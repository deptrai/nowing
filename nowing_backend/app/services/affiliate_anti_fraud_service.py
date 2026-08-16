class AffiliateAntiFraudService:
    @staticmethod
    def evaluate_payout_risk(payout_id: int) -> dict:
        return {"risk_score": 10, "status": "Low Risk"}
