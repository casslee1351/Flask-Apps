def stability_class(cv: float) -> str:
    
    if cv is None:
        return "N/A"
    if cv < 0.25:
        return "stable"
    elif cv < 0.50:
        return "moderate"
    return "unstable"
