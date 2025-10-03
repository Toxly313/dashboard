# charts.py
import plotly.graph_objects as go
from ui_theme import apply_fig_style, ORANGE, ORANGE_DARK

def bar_grouped(x, prev_vals, cur_vals, colors=None, title=""):
    fig = go.Figure()
    fig.add_bar(name="Vorher", x=x, y=prev_vals, marker_color="#CBD5E1")
    fig.add_bar(name="Nachher", x=x, y=cur_vals, marker_color=colors or ORANGE)
    return apply_fig_style(fig, title, 300)

def area_soft(x, y1, y2=None, title=""):
    fig = go.Figure()
    fig.add_scatter(x=x, y=y1, mode="lines", fill="tozeroy", line=dict(width=2))
    if y2 is not None:
        fig.add_scatter(x=x, y=y2, mode="lines", fill="tozeroy", line=dict(width=2, dash="dot"))
    return apply_fig_style(fig, title, 260)

def donut(value: float, title=""):
    fig = go.Figure(go.Pie(
        values=[value, 100-value],
        labels=[f"{value:.0f}%", ""],
        hole=.75,
        sort=False,
        direction="clockwise",
        textinfo="label",
        marker=dict(colors=[ORANGE, "#F1F5F9"])
    ))
    fig.update_traces(showlegend=False)
    return apply_fig_style(fig, title, 280)
