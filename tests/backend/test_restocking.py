"""
Tests for the restocking endpoints.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server"))

from main import RESTOCK_LEAD_TIME_DAYS


class TestRestockRecommendations:
    """Tests for GET /api/restocking/recommendations"""

    def test_zero_budget_returns_no_items(self, client):
        """A zero budget recommends nothing"""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total_cost"] == 0
        assert data["lead_time_days"] == 0

    def test_total_cost_stays_within_budget(self, client):
        """Spend never exceeds the budget, and the numbers add up"""
        for budget in [1000, 25000, 100000, 500000]:
            data = client.get(f"/api/restocking/recommendations?budget={budget}").json()
            assert data["total_cost"] <= budget
            assert round(data["total_cost"] + data["remaining_budget"], 2) == budget
            assert round(sum(i["line_total"] for i in data["items"]), 2) == data["total_cost"]

    def test_larger_budget_buys_at_least_as_many_units(self, client):
        """More budget never reduces the units recommended"""
        small = client.get("/api/restocking/recommendations?budget=20000").json()
        large = client.get("/api/restocking/recommendations?budget=200000").json()
        assert sum(i["quantity"] for i in large["items"]) >= sum(i["quantity"] for i in small["items"])

    def test_quantity_never_exceeds_shortfall(self, client):
        """No item is ordered beyond the gap between forecast and stock"""
        data = client.get("/api/restocking/recommendations?budget=500000").json()
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert 0 < item["quantity"] <= item["shortfall"]

    def test_lead_time_is_longest_item_lead_time(self, client):
        """The order lead time matches the slowest category among its items"""
        data = client.get("/api/restocking/recommendations?budget=500000").json()
        expected = max(RESTOCK_LEAD_TIME_DAYS[i["category"]] for i in data["items"])
        assert data["lead_time_days"] == expected

    def test_negative_budget_returns_400(self, client):
        """A negative budget is rejected"""
        response = client.get("/api/restocking/recommendations?budget=-1")
        assert response.status_code == 400


class TestRestockOrders:
    """Tests for POST and GET /api/restocking-orders"""

    def test_create_order_returns_201_and_appears_in_list(self, client):
        """A submitted order is stored and listed"""
        response = client.post("/api/restocking-orders", json={"budget": 50000})
        assert response.status_code == 201
        order = response.json()
        assert order["status"] == "Submitted"
        assert order["total_cost"] <= 50000
        assert order["lead_time_days"] > 0
        assert order["order_date"] < order["expected_delivery"]

        listed = client.get("/api/restocking-orders").json()
        assert order["order_number"] in [o["order_number"] for o in listed]

    def test_newest_order_is_listed_first(self, client):
        """The list is ordered newest first"""
        client.post("/api/restocking-orders", json={"budget": 10000})
        newest = client.post("/api/restocking-orders", json={"budget": 20000}).json()
        listed = client.get("/api/restocking-orders").json()
        assert listed[0]["order_number"] == newest["order_number"]

    def test_zero_budget_returns_400(self, client):
        """An order that buys nothing is rejected"""
        response = client.post("/api/restocking-orders", json={"budget": 0})
        assert response.status_code == 400

    def test_negative_budget_returns_400(self, client):
        """A negative budget is rejected"""
        response = client.post("/api/restocking-orders", json={"budget": -5})
        assert response.status_code == 400

    def test_order_does_not_change_customer_orders(self, client):
        """Restocking orders stay out of the customer orders list"""
        before = len(client.get("/api/orders").json())
        client.post("/api/restocking-orders", json={"budget": 30000})
        after = len(client.get("/api/orders").json())
        assert before == after
