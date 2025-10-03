# charts.py
import plotly.graph_objects as go
from ui_theme import style_fig, PURPLE, TEAL

def bar_compare(x, series_a, series_b, labels=("Series A","Series B"), title=""):
    fig = go.Figure()
    fig.add_bar(name=labels[0], x=x, y=series_a, marker_color=TEAL)
    fig.add_bar(name=labels[1], x=x, y=series_b, marker_color=PURPLE)
    return style_fig(fig, title, h=300)

def donut(value, title=""):
    fig = go.Figure(go.Pie(
        values=[value, 100-value],
        labels=[f"{value:.0f}%", ""],
        hole=.7,
        marker=dict(colors=[PURPLE, "#EEF2FF"]),
        textinfo="label",
        sort=False
    ))
    fig.update_traces(showlegend=False)
    return style_fig(fig, title, h=260)

def line_trend(x, y, title=""):
    fig = go.Figure()
    fig.add_scatter(x=x, y=y, mode="lines+markers", line=dict(width=3, color=PURPLE))
    return style_fig(fig, title, h=260)

def tiny_spark(x, y):
    fig = go.Figure()
    fig.add_scatter(x=x, y=y, mode="lines", line=dict(width=2, color="#C4B5FD"))
    fig.update_layout(
        template="plotly_white",
        height=120, margin=dict(t=0,l=0,r=0,b=0), showlegend=False,
        xaxis=dict(visible=False), yaxis=dict(visible=False)
    )
    return fig
