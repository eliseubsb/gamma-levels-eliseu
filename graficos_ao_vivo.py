import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd

def _plot_estilo_pro(titulo, tk_yf, spot_usd, raz_conv, decs, df_sub, cw, pw, vn, dfp, gf, ticker_lbl):
    try:
        h = yf.Ticker(tk_yf).history(period='2d', interval='1m')
    except Exception:
        h = pd.DataFrame()
    if h.empty:
        st.warning(f'Aguardando candles de 1 minuto (2 dias) para {titulo}.')
        return
    h = h.dropna(subset=['Open','High','Low','Close']).copy()
    try:
        idx_br = h.index.tz_convert('America/Sao_Paulo') if h.index.tz is not None else h.index
    except Exception:
        idx_br = h.index
    lbl_tempo = [dt.strftime('%d/%m %H:%M') for dt in idx_br]
    nb = len(h)
    xs = list(range(nb))
    conv = lambda v: round((float(v) * raz_conv) / 5.0) * 5.0 if raz_conv != 1.0 else round(float(v), decs)
    fig = go.Figure(data=[go.Candlestick(x=xs, open=h['Open'], high=h['High'], low=h['Low'], close=h['Close'], text=lbl_tempo, increasing_line_color='#00e676', decreasing_line_color='#ff1744', name=titulo)])
    estrut = [
        (f'Call Wall (OI {int(cw.oi/1000)}k) - resistencia estrutural (MM vende rali)', conv(cw.strike), '#ff1744', 'solid', 100),
        (f'Vanna+ (OI {int(vn.oi/1000)}k) - fluxo comprador se IV cair', conv(vn.strike), '#00e676', 'dash', 95),
        ('Delta Flip - zero-cross do delta liquido', conv(dfp), '#ce93d8', 'solid', 92),
        ('Gamma Flip - divisor de regime long/short gamma', conv(gf), '#ffd600', 'dash', 98),
        (f'Spot Ref ({ticker_lbl} ${spot_usd:.2f})', conv(spot_usd), '#b0bec5', 'dot', 90),
        (f'Put Wall (OI {int(pw.oi/1000)}k) - suporte estrutural (MM compra queda)', conv(pw.strike), '#29b6f6', 'solid', 100)
    ]
    niveis = list(estrut)
    if not df_sub.empty and spot_usd > 0:
        sub = df_sub[(df_sub['strike'] >= spot_usd*0.90) & (df_sub['strike'] <= spot_usd*1.10)].copy()
        if 'volume' not in sub.columns: sub['volume'] = 0
        if 'gex_oi' not in sub.columns: sub['gex_oi'] = 0
        if 'dex_oi' not in sub.columns: sub['dex_oi'] = 0
        aggs = []
        for k, gk in sub.groupby('strike'):
            c_oi = float(gk[gk['is_c']]['openInterest'].sum())
            p_oi = float(gk[~gk['is_c']]['openInterest'].sum())
            vol_t = float(gk['volume'].fillna(0).sum())
            g_net = float(gk['gex_oi'].fillna(0).sum())
            d_net = float(gk['dex_oi'].fillna(0).sum())
            imp = c_oi + p_oi + vol_t * 2.0 + abs(g_net)/1e4
            aggs.append((imp, float(k), c_oi, p_oi, vol_t, g_net, d_net))
        aggs.sort(reverse=True)
        mg = max([1.0] + [abs(gn) for _, _, _, _, _, gn, _ in aggs])
        md = max([1.0] + [abs(dn) for _, _, _, _, _, _, dn in aggs])
        mo = max([1.0] + [co + po for _, _, co, po, _, _, _ in aggs])
        mv = max([1.0] + [vt for _, _, _, _, vt, _, _ in aggs])
        dy = (h['High'].max() - h['Low'].min()) * 0.015 or (0.05 if raz_conv == 1.0 else 95.0)
        dados_barras = {}
        for imp, k, c_oi, p_oi, vol_t, g_net, d_net in aggs:
            yv = conv(k)
            lc = 'OTM' if k > spot_usd else 'ITM'
            lp = 'ITM' if k > spot_usd else 'OTM'
            tag = 'Gamma Wall (MM defende)' if g_net >= 0 else 'Gamma Risk (acelera)'
            cor_k = '#69f0ae' if g_net >= 0 else '#ff8a80'
            w_str = f' | WIN {int(yv):,}'.replace(',', '.') if raz_conv != 1.0 else ''
            txt = f'{ticker_lbl} ${k:.2f}{w_str} · {int(c_oi/1000)}k C({lc}) · {int(p_oi/1000)}k P({lp}) · {tag}'
            niveis.append((txt, yv, cor_k, 'dot', imp))
            dados_barras[yv] = (g_net, d_net, c_oi + p_oi, vol_t)
    usados = []
    min_g = 0.038 if raz_conv == 1.0 else 80.0
    for txt, yv, cor, stl, _ in niveis:
        if yv > 0 and all(abs(yv - u) > min_g for u in usados):
            usados.append(yv)
            fig.add_shape(type='line', x0=0, x1=nb+1, y0=yv, y1=yv, line=dict(color=cor, width=1.6, dash=stl))
            fig.add_annotation(x=nb+1, y=yv, text=f' <b>{txt}</b> ', showarrow=False, xanchor='left', bgcolor='#0c161e', bordercolor=cor, borderwidth=1.5, borderpad=4, font=dict(color='#ffffff', size=18))
            if yv in dados_barras:
                g_net, d_net, oi_tot, vol_t = dados_barras[yv]
                wg = max(1.0, abs(g_net)/mg * 3.0)
                wd = max(1.0, abs(d_net)/md * 3.0)
                wo = max(1.0, oi_tot/mo * 3.0)
                wv = max(1.0, vol_t/mv * 3.0)
                if g_net >= 0:
                    fig.add_shape(type='rect', x0=nb+157, x1=nb+157+wg, y0=yv-dy/2, y1=yv+dy/2, fillcolor='rgba(156,39,176,0.85)', line=dict(width=0))
                    fig.add_annotation(x=nb+157+wg+0.6, y=yv, text=f'<b>GEX {g_net/1e6:+.1f}M</b>', showarrow=False, xanchor='left', font=dict(color='#ffffff', size=17))
                else:
                    fig.add_shape(type='rect', x0=nb+157-wg, x1=nb+157, y0=yv-dy/2, y1=yv+dy/2, fillcolor='rgba(255,23,68,0.85)', line=dict(width=0))
                    fig.add_annotation(x=nb+157-wg-0.6, y=yv, text=f'<b>GEX {g_net/1e6:+.1f}M</b>', showarrow=False, xanchor='right', font=dict(color='#ffd600', size=17))
                if d_net >= 0:
                    fig.add_shape(type='rect', x0=nb+211, x1=nb+211+wd, y0=yv-dy/2, y1=yv+dy/2, fillcolor='rgba(0,230,118,0.85)', line=dict(width=0))
                    fig.add_annotation(x=nb+211+wd+0.6, y=yv, text=f'<b>DEX {d_net/1e6:+.1f}M</b>', showarrow=False, xanchor='left', font=dict(color='#ffffff', size=17))
                else:
                    fig.add_shape(type='rect', x0=nb+211-wd, x1=nb+211, y0=yv-dy/2, y1=yv+dy/2, fillcolor='rgba(255,87,34,0.85)', line=dict(width=0))
                    fig.add_annotation(x=nb+211-wd-0.6, y=yv, text=f'<b>DEX {d_net/1e6:+.1f}M</b>', showarrow=False, xanchor='right', font=dict(color='#ffd600', size=17))
                fig.add_shape(type='rect', x0=nb+241, x1=nb+241+wo, y0=yv-dy/2, y1=yv+dy/2, fillcolor='rgba(41,182,246,0.80)', line=dict(width=0))
                fig.add_annotation(x=nb+241+wo+0.6, y=yv, text=f'<b>OI {int(oi_tot/1000)}k</b>', showarrow=False, xanchor='left', font=dict(color='#ffffff', size=17))
                fig.add_shape(type='rect', x0=nb+269, x1=nb+269+wv, y0=yv-dy/2, y1=yv+dy/2, fillcolor='rgba(255,214,0,0.80)', line=dict(width=0))
                fig.add_annotation(x=nb+269+wv+0.6, y=yv, text=f'<b>VOL {int(vol_t/1000)}k</b>', showarrow=False, xanchor='left', font=dict(color='#ffffff', size=17))
    for x_sep in [nb+130, nb+184, nb+238, nb+266]:
        fig.add_shape(type='line', x0=x_sep, x1=x_sep, yref='paper', y0=0, y1=1, line=dict(color='#455a64', width=1.4, dash='dash'))
    for x_lbl, txt_c in [(nb+157, 'GEX'), (nb+211, 'DEX'), (nb+252, 'OPEN INTEREST'), (nb+281, 'VOL')]:
        fig.add_annotation(x=x_lbl, yref='paper', y=1.01, text=f'<b>{txt_c}</b>', showarrow=False, xanchor='center', yanchor='bottom', font=dict(color='#e0e0e0', size=13.5))
    passo = max(1, nb // 16)
    t_vals = list(range(0, nb, passo))
    t_txts = [lbl_tempo[i] for i in t_vals]
    x_ini = max(0, nb - 130)
    fig.update_layout(title=titulo, template='plotly_dark', height=840, dragmode='pan', xaxis_rangeslider_visible=False, xaxis=dict(range=[x_ini, nb+298], tickmode='array', tickvals=t_vals, ticktext=t_txts, tickfont=dict(color='#ffffff', size=12.5), linecolor='#546e7a', showline=True, gridcolor='#15202b'), yaxis=dict(side='right', fixedrange=False, tickfont=dict(color='#ffffff', size=13), linecolor='#546e7a', showline=True, gridcolor='#15202b'), margin=dict(l=12,r=15,t=56,b=36), plot_bgcolor='#060b10', paper_bgcolor='#060b10')
    st.plotly_chart(fig, width='stretch', config={'scrollZoom': True, 'displayModeBar': True})

def render_graficos_tempo_real(ticker, spot, win_spot, df_sub, cw, pw, vn, dfp, gf):
    st.subheader(f'📈 GRAFICO TEMPO REAL (1 MIN • 2 DIAS) - {ticker} (USD) | OI TOTAL • GEX • DEX • VOL')
    tk_yf = 'ELET3.SA' if ticker == 'EBR' else ticker.replace('.', '-')
    _plot_estilo_pro(f'{ticker} (USD) - Soma Todos Vencimentos (Calls/Puts • GEX • DEX • Vol)', tk_yf, spot, 1.0, 2, df_sub, cw, pw, vn, dfp, gf, ticker)
    st.subheader(f'🇧🇷 GRAFICO TEMPO REAL (1 MIN • 2 DIAS) - WIN / IBOV (PONTOS) | REGIOES DE {ticker}')
    raz = (win_spot / spot) if spot > 0 else 5050.0
    _plot_estilo_pro(f'WIN / IBOV - Regioes de {ticker} Convertidas (Calls/Puts • GEX • DEX • Vol)', '^BVSP', spot, raz, 0, df_sub, cw, pw, vn, dfp, gf, ticker)
