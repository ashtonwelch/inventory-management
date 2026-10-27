<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card budget-card">
      <div class="budget-header">
        <label for="budget-slider" class="budget-label">{{ t('restocking.budget') }}</label>
        <div class="budget-value">{{ money(budget) }}</div>
      </div>
      <input
        id="budget-slider"
        v-model.number="budget"
        type="range"
        min="0"
        max="500000"
        step="5000"
        class="budget-slider"
      />
      <div class="budget-scale">
        <span>{{ money(0) }}</span>
        <span>{{ money(500000) }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ money(budget) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.plannedSpend') }}</div>
          <div class="stat-value">{{ money(totalCost) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ money(remainingBudget) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.leadTime') }}</div>
          <div class="stat-value">{{ leadTimeDays }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            {{ t('restocking.recommendations') }} ({{ items.length }})
            <span v-if="updating" class="updating">{{ t('restocking.updating') }}</span>
          </h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="items.length === 0 || submitting || updating"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="orderError" class="order-message order-error" role="alert">{{ orderError }}</div>
        <div v-if="confirmation" class="order-message order-success" role="status">
          {{ t('restocking.confirmation', {
            orderNumber: confirmation.order_number,
            date: formatDate(confirmation.expected_delivery)
          }) }}
        </div>

        <div v-if="items.length === 0" class="empty-state">{{ t('restocking.empty') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th class="num">{{ t('restocking.table.shortfall') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.item_sku">
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ translateProductName(item.item_name) }}</td>
                <td>{{ item.category }}</td>
                <td class="num">{{ item.shortfall.toLocaleString() }}</td>
                <td class="num">{{ item.quantity.toLocaleString() }}</td>
                <td class="num">{{ money(item.unit_cost) }}</td>
                <td class="num"><strong>{{ money(item.line_total) }}</strong></td>
                <td class="num">{{ item.lead_time_days }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale, translateProductName } = useI18n()

    const budget = ref(100000)
    const loading = ref(true)
    const updating = ref(false)
    const error = ref(null)
    const items = ref([])
    const totalCost = ref(0)
    const remainingBudget = ref(0)
    const leadTimeDays = ref(0)

    const submitting = ref(false)
    const orderError = ref(null)
    const confirmation = ref(null)

    const money = (amount) => formatCurrency(amount, currentCurrency.value)

    const formatDate = (dateString) => {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return dateString
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    }

    let requestId = 0
    const loadRecommendations = async () => {
      const myId = ++requestId
      updating.value = true
      try {
        const data = await api.getRestockRecommendations(budget.value)
        if (myId !== requestId) return
        items.value = data.items || []
        totalCost.value = data.total_cost || 0
        remainingBudget.value = data.remaining_budget ?? 0
        leadTimeDays.value = data.lead_time_days || 0
        error.value = null
      } catch (err) {
        if (myId !== requestId) return
        error.value = t('restocking.loadError') + ': ' + err.message
      } finally {
        if (myId === requestId) {
          loading.value = false
          updating.value = false
        }
      }
    }

    let debounceTimer = null
    watch(budget, () => {
      confirmation.value = null
      orderError.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(loadRecommendations, 300)
    })

    const placeOrder = async () => {
      if (submitting.value || items.value.length === 0) return
      submitting.value = true
      orderError.value = null
      confirmation.value = null
      try {
        confirmation.value = await api.createRestockOrder(budget.value)
      } catch (err) {
        orderError.value = err.response?.data?.detail || t('restocking.orderError')
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)
    onBeforeUnmount(() => {
      clearTimeout(debounceTimer)
      requestId++
    })

    return {
      t,
      budget,
      loading,
      updating,
      error,
      items,
      totalCost,
      remainingBudget,
      leadTimeDays,
      submitting,
      orderError,
      confirmation,
      money,
      formatDate,
      placeOrder,
      translateProductName
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
  padding: 1.5rem;
}

.budget-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 1rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #64748b;
}

.budget-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: #0f172a;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.updating {
  font-size: 0.813rem;
  font-weight: 400;
  color: #64748b;
  margin-left: 0.5rem;
}

.place-order-btn {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.order-message {
  margin: 0 1.5rem 1rem;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.order-success {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
}

.order-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.num {
  text-align: right;
}
</style>
