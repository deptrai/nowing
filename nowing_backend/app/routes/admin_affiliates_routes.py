from fastapi import APIRouter

router = APIRouter()

@router.get("/payouts")
def get_payouts():
    return []

@router.post("/payouts/{id}/approve")
def approve_payout(id: int):
    return {"status": "approved"}

@router.post("/payouts/{id}/reject")
def reject_payout(id: int):
    return {"status": "rejected"}
