def build_insights(data: dict) -> list[dict]:
    """
    Liefert priorisierte Empfehlungen mit zusätzliche Feldern:
    - impact_score: 0–10
    - effort: 'low' | 'medium' | 'high'
    - savings_eur: geschätzte monatliche Ersparnis / Mehrertrag (float)
    - kpis: betroffene KPIs (Liste)
    """
    out = []
    
    # Daten extrahieren und sicher konvertieren
    belegt = int(data.get("belegt", 0))
    frei = int(data.get("frei", 0))
    tot = belegt + frei if (belegt + frei) > 0 else 1
    occ = (belegt / tot * 100) if tot else float(data.get("belegungsgrad", 0))
    
    vd = float(data.get("vertragsdauer_durchschnitt", 0) or 0)
    
    pay = data.get("zahlungsstatus", {}) or {}
    paid = int(pay.get("bezahlt", 0))
    open_ = int(pay.get("offen", 0))
    over = int(pay.get("überfällig", 0))
    
    her = data.get("kundenherkunft", {}) or {}
    online = int(her.get("Online", 0))
    emp = int(her.get("Empfehlung", 0))
    walk = int(her.get("Vorbeikommen", 0))
    
    google = int(data.get("social_google", 0))
    fb = int(data.get("social_facebook", 0))

    # 1) Auslastung zu niedrig
    if occ < 85:
        out.append(dict(
            title="Auslastung steigern (Kurzfrist-Aktion)",
            impact="hoch", impact_score=9, effort="low", savings_eur=300.0,
            kpis=["Belegungsgrad", "Belegt", "Frei"],
            analysis=f"Aktuelle Auslastung {occ:.1f} % bei {belegt}/{tot} Einheiten.",
            actions=[
                "2-Wochen-Aktion: −10 % für Neukunden (Mindestlaufzeit ≥ 3 Monate).",
                "Bundles: Vorauszahlung → 1. Monat gratis.",
                "Preisstaffel für kleine Einheiten."
            ]
        ))

    # 2) Vollauslastung → Preise anheben
    elif occ >= 95:
        out.append(dict(
            title="Preisoptimierung bei Vollauslastung",
            impact="mittel", impact_score=7, effort="low", savings_eur=200.0,
            kpis=["Belegungsgrad"],
            analysis=f"Sehr hohe Auslastung ({occ:.1f} %): Preissensitivität sinkt.",
            actions=[
                "Preise kleiner Einheiten testweise +3–5 %.",
                "Warteliste & Lead-Capture auf Landingpage."
            ]
        ))

    # 3) Forderungen
    if over > 0 or open_ > 0:
        out.append(dict(
            title="Mahnwesen automatisieren",
            impact="hoch", impact_score=8, effort="medium", savings_eur=250.0,
            kpis=["Zahlungsstatus"],
            analysis=f"{paid} bezahlt, {open_} offen, {over} überfällig.",
            actions=[
                "E-Mail + SMS am Fälligkeitstag; nach 7 Tagen Mahnstufe 1.",
                "Skonto 2 % bei Zahlung ≤ 7 Tage (Cashflow-Boost)."
            ]
        ))

    # 4) Vertragsdauer / Churn-Risiko
    if vd and vd < 6:
        out.append(dict(
            title="Retention-Programm (Vertragsverlängerung)",
            impact="mittel", impact_score=6, effort="medium", savings_eur=150.0,
            kpis=["Ø Vertragsdauer", "Belegt"],
            analysis=f"Ø Vertragsdauer {vd:.1f} Monate → erhöhtes Kündigungsrisiko.",
            actions=[
                "4 Wochen vor Ende: Upgrade-Angebot (größere Einheit −5 % im 1. Monat).",
                "Reminder-Sequenz (E-Mail/SMS) inkl. Vorteilsargumentation."
            ]
        ))

    # 5) Online-Leads skalieren (wenn Empfehlungen > Online-Leads)
    tot_leads = online + emp + walk
    if tot_leads > 0 and online < emp:
        out.append(dict(
            title="Online-Leads skalieren",
            impact="mittel", impact_score=7, effort="low", savings_eur=120.0,
            kpis=["Social/Online", "Leads"],
            analysis=f"Lead-Mix: Online {online}, Empfehlung {emp}, Vorbeikommen {walk}.",
            actions=[
                "Google Business: 10 neue Fotos + 5 frische Bewertungen.",
                "LP-Optimierung (sofortige Preisabfrage)."
            ]
        ))

    # 6) Empfehlungsrate
    if emp < 5:
        out.append(dict(
            title="Referral-Programm",
            impact="niedrig", impact_score=5, effort="low", savings_eur=80.0,
            kpis=["Leads", "Empfehlungen"],
            analysis="Empfehlungsrate ist gering.",
            actions=[
                "25 € Guthaben pro geworbenem Neukunden.",
                "Dankes-Karte + QR-Code zur Bewertung."
            ]
        ))

    # 7) Reviews
    if google < 60:
        out.append(dict(
            title="Review-Boost (Google)",
            impact="mittel", impact_score=6, effort="low", savings_eur=60.0,
            kpis=["Google Reviews"],
            analysis=f"Nur {google} Google-Reviews → Social Proof ausbaufähig.",
            actions=[
                "2-wöchige Bewertungsaktion mit Follow-up E-Mail.",
            ]
        ))

    # 8) Facebook Spend feintunen
    if fb > 200 and occ < 90:
        out.append(dict(
            title="FB-Targeting schärfen",
            impact="niedrig", impact_score=4, effort="medium", savings_eur=50.0,
            kpis=["Facebook", "Belegungsgrad"],
            analysis=f"Hoher FB-Traffic ({fb}) bei Auslastung {occ:.0f} %.",
            actions=[
                "Zielgruppe: Umzug/Studierende, Click-to-Call.",
                "Budget auf performante Anzeigengruppen bündeln."
            ]
        ))

    # Sortierung: erst Impact-Score, dann Ersparnis
    out.sort(key=lambda x: (x.get("impact_score", 0), x.get("savings_eur", 0)), reverse=True)
    return out
