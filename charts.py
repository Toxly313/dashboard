import plotly.graph_objects as go
from .state import next_chart_key

def occ_chart(prev, cur):
    belegt_cur = cur.get("belegt",0); belegt_prev = prev.get("belegt",0)
    frei_cur = cur.get("frei",0); frei_prev = prev.get("frei",0)

    fig = go.Figure()
    fig.add_bar(name="Vorher", x=["Belegt","Frei"], y=[belegt_prev, frei_prev], marker_color="#B0B0B0", opacity=0.5)
    fig.add_bar(name="Nachher", x=["Belegt","Frei"], y=[belegt_cur, frei_cur])
    fig.update_layout(title="Auslastung: Belegt vs. Frei", barmode="group", height=320, margin=dict(t=40,b=40))
    return fig, next_chart_key("occ")

def pay_chart(prev, cur):
    keys = ["bezahlt","offen","überfällig"]
    pay_prev = [prev.get("zahlungsstatus",{}).get(k,0) for k in keys]
    pay_cur  = [cur.get("zahlungsstatus",{}).get(k,0) for k in keys]
    fig = go.Figure()
    fig.add_bar(name="Vorher", x=[k.title() for k in keys], y=pay_prev, marker_color="#B0B0B0", opacity=0.5)
    fig.add_bar(name="Nachher", x=[k.title() for k in keys], y=pay_cur)
    fig.update_layout(title="Zahlungsstatus", barmode="group", height=320, margin=dict(t=40,b=40))
    return fig, next_chart_key("pay")

def source_chart(prev, cur):
    her_prev = prev.get("kundenherkunft", {}) or {}
    her_cur  = cur.get("kundenherkunft", {}) or {}
    channels = sorted(set(her_prev.keys()) | set(her_cur.keys()))
    prev_h = [her_prev.get(k, 0) for k in channels]
    cur_h  = [her_cur.get(k, 0) for k in channels]
    fig = go.Figure()
    fig.add_bar(name="Vorher", x=channels, y=prev_h, marker_color="#B0B00", opacity=0.5)
    fig.add_bar(name="Nachher", x=channels, y=cur_h)
    fig.update_layout(title="Kundenherkunft", barmode="group", height=340, margin=dict(t=40,b=40))
    return fig, next_chart_key("src")
