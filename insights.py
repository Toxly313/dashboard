def build_insights(data: dict) -> list[dict]:
    out = []
    belegt = data.get("belegt",0); frei = data.get("frei",0)
    tot = (belegt or 0) + (frei or 0)
    occ = (belegt/tot*100) if tot else data.get("belegungsgrad",0)
    vd = data.get("vertragsdauer_durchschnitt",0)
    pay = data.get("zahlungsstatus",{}) or {}
    paid, open_, over = pay.get("bezahlt",0), pay.get("offen",0), pay.get("überfällig",0)
    her = data.get("kundenherkunft",{}) or {}
    online, emp, walk = her.get("Online",0), her.get("Empfehlung",0), her.get("Vorbeikommen",0)
    google = data.get("social_google",0); fb = data.get("social_facebook",0)

    if occ < 85:
        out.append(dict(title="Auslastung unter 85 %", impact="hoch",
                        analysis=f"Aktuelle Auslastung {occ:.1f} % bei {belegt}/{tot} Einheiten.",
                        actions=["2-Wochen-Aktion −10 % (LZ ≥ 3 Monate).",
                                 "Preisstaffeln; Bundle (1. Monat gratis bei Vorauszahlung)."]))
    elif occ >= 95:
        out.append(dict(title="Nahe Vollauslastung", impact="mittel",
                        analysis=f"Auslastung {occ:.1f} %. Preissensitivität sinkt.",
                        actions=["Preise kleiner Einheiten +3–5 % testen.",
                                 "Warteliste/Lead-Capture."]))

    if over > 0 or open_ > 0:
        out.append(dict(title="Offene/überfällige Rechnungen", impact="hoch",
                        analysis=f"{paid} bezahlt, {open_} offen, {over} überfällig.",
                        actions=["Automatisches Mahnwesen (E-Mail/SMS).",
                                 "Ziel: < 5 offene/überfällige Rechnungen."]))

    if vd and vd < 6:
        out.append(dict(title="Kurze Vertragsdauer → Churn-Risiko", impact="mittel",
                        analysis=f"Ø Vertragsdauer {vd:.1f} Monate.",
                        actions=["4 Wochen vor Ende: Upgrade-Angebot (größere Einheit −5 % im 1. Monat).",
                                 "Retention-Flows."]))

    tot_leads = online + emp + walk
    if tot_leads>0 and online < emp:
        out.append(dict(title="Empfehlungen > Online", impact="mittel",
                        analysis=f"Lead-Mix Online {online}, Empfehlung {emp}, Vorbeikommen {walk}.",
                        actions=["Google Business: 10 neue Fotos + 5 frische Bewertungen.",
                                 "FAQ & Preise klarer."]))

    if emp < 5:
        out.append(dict(title="Niedrige Empfehlungsrate", impact="niedrig",
                        analysis="Wenig organische Empfehlungen.",
                        actions=["Referral-Programm: 25 € Guthaben.",
                                 "Danke-Karten + QR-Code zur Bewertung."]))

    if google < 60:
        out.append(dict(title="Wenig Google-Reviews", impact="mittel",
                        analysis=f"Aktuell {google} Reviews.",
                        actions=["Review-Push 2 Wochen."]))

    if fb > 200 and occ < 90:
        out.append(dict(title="Facebook-Spend neu ausrichten", impact="niedrig",
                        analysis=f"{fb} FB-Signal bei Auslastung {occ:.0f} %.",
                        actions=["Targeting Umzug/Studierende, Click-to-Call, Sofort-Preis Landingpage."]))
    return out
