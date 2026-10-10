def calculate_risk(error_rate: float, latency_ms: float, health_status: str) -> dict:
    error_points = min(error_rate * 4, 40)
    latency_points = min(max((latency_ms - 200) / 20, 0), 30)
    health_points = 30 if health_status.lower() == "unhealthy" else 0
    score = round(min(error_points + latency_points + health_points, 100), 1)

    if score >= 70:
        level = "HIGH"
        rec = "High risk. Investigate immediately and consider rolling back to the last stable version."
    elif score >= 30:
        level = "MEDIUM"
        rec = "Moderate risk. Review error and latency trends and keep monitoring before promoting."
    else:
        level = "LOW"
        rec = "Low risk. Signals look normal. Continue monitoring."
    return {"risk_score": score, "risk_level": level, "recommendation": rec}
