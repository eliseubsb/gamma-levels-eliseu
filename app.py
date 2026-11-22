import datetime, re, urllib.parse, numpy as np, pandas as pd, plotly.graph_objects as go, streamlit as st, yfinance as yf
from curl_cffi import requests as cffi_requests
from plotly.subplots import make_subplots
from scipy.stats import norm
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(page_title='Gamma Levels Terminal', page_icon='⚡', layout='wide')
st.markdown('<style>.stApp{background-color:#070d12;color:#ffffff;} label, label * {color:#ffffff !important;} div[data-testid="stMetric"]{background-color:#0d1922;border:1px solid #234052;padding:14px;border-radius:8px;} .tbl-gama{width:100%;border-collapse:collapse;background:#0d1922;color:#ffffff;font-size:14px;margin-bottom:16px;} .tbl-gama th{background:#132533;color:#80d8ff;text-align:left;padding:10px;border:1px solid #234052;} .tbl-gama td{padding:9px 10px;border:1px solid #234052;color:#ffffff !important;}</style>', unsafe_allow_html=True)

c1, c2 = st.columns([3, 1])
c1.markdown('### ⚡ HEDGE MAP & GAMMA TERMINAL (CBOE + BARCHART)')
ticker = c2.selectbox('Ativo', ['EWZ', 'SPY', 'QQQ', 'IWM', 'PBR', 'VALE'], label_visibility='collapsed')

def greeks_bs(S, K, T, r, sig, call=True):
    T, sig = np.maximum(T, 1e-5), np.maximum(sig, 1e-4)
    d1 = (np.log(S/K) + (r + 0.5*sig**2)*T) / (sig*np.sqrt(T))
    d2 = d1 - sig*np.sqrt(T)
    pdf = norm.pdf(d1)
    d = norm.cdf(d1) if call else norm.cdf(d1) - 1.0
    return d, pdf/(S*sig*np.sqrt(T)), -pdf*(d2/sig)

@st.cache_data(ttl=30)
def load_chain(sym):
    sess = cffi_requests.Session(impersonate='chrome124')
    sess.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', 'Accept': 'application/json, text/plain, */*', 'Referer': 'https://cboe.com'})
    fonte = 'Yahoo Finance (Backup)'
    spot, df_final = None, pd.DataFrame()
    try:
        r = sess.get(f'https://cboe.com{sym}.json', timeout=8)
        if r.status_code == 200:
            raw = r.json().get('data', {})
            opts = raw.get('options', [])
            spot = float(raw.get('current_price'))
            parsed = []
            pat = re.compile(r'^[A-Z]+(\d{6})([CP])(\d{8})$')
            for o in opts:
                m = pat.match(o.get('option', ''))
                if not m: continue
                exp_raw, cp, k_raw = m.groups()
                oi, vol = float(o.get('open_interest') or 0), float(o.get('volume') or 0)
                if oi == 0 and vol == 0: continue
                k = int(k_raw) / 1000.0
                is_c = (cp == 'C')
                g, d, iv = float(o.get('gamma') or 0), float(o.get('delta') or 0), float(o.get('iv') or 0.25)
                exp_full = f'20{exp_raw[:2]}-{exp_raw[2:4]}-{exp_raw[4:6]}'
                parsed.append({'strike': k, 'is_c': is_c, 'openInterest': oi, 'volume': vol, 'gamma': g, 'delta': d, 'iv': iv, 'exp': exp_full[2:], 'exp_full': exp_full})
            if parsed:
                df_final = pd.DataFrame(parsed)
                sv = np.where(df_final['is_c'], 1.0, -1.0)
                df_final['gex_oi'] = sv * df_final['gamma'] * df_final['openInterest'] * 100 * (spot**2) * 0.01
                df_final['gex_vol'] = sv * df_final['gamma'] * df_final['volume'] * 100 * (spot**2) * 0.01
                df_final['dex_oi'] = df_final['delta'] * df_final['openInterest'] * 100 * spot
                df_final['dex_vol'] = df_final['delta'] * df_final['volume'] * 100 * spot
                df_final['van_oi'] = -df_final['gamma'] * df_final['openInterest'] * 100 * spot * 0.1
                fonte = 'CBOE Oficial (Feed Direto)'
    except Exception:
        pass
    if df_final.empty:
        try:
            tk = yf.Ticker(sym)
            hist_s = tk.history(period='5d')['Close'].dropna()
            spot = float(hist_s.iloc[-1]) if not hist_s.empty else 28.54
            now, rows = datetime.datetime.now(), []
            for exp in tk.options[:20]:
                T = max((datetime.datetime.strptime(exp,'%Y-%m-%d') + datetime.timedelta(hours=16) - now).total_seconds()/31536000.0, 1/365.0)
                ch = tk.option_chain(exp)
                for is_c, df in [(True, ch.calls), (False, ch.puts)]:
                    df = df.fillna({'openInterest':0, 'volume':0, 'impliedVolatility':0.25})
                    df = df[(df['openInterest']>0) | (df['volume']>0)].copy()
                    if df.empty: continue
                    d, g, v = greeks_bs(spot, df['strike'].values, T, 0.045, df['impliedVolatility'].values, is_c)
                    sv = 1.0 if is_c else -1.0
                    df['gex_oi'], df['gex_vol'] = sv * g * df['openInterest'] * 100 * spot**2 * 0.01, sv * g * df['volume'] * 100 * spot**2 * 0.01
                    df['dex_oi'], df['dex_vol'] = d * df['openInterest'] * 100 * spot, d * df['volume'] * 100 * spot
                    df['van_oi'], df['is_c'], df['exp'] = v * df['openInterest'] * 100 * spot, is_c, exp[2:]
                    rows.append(df)
            if rows:
                df_final = pd.concat(rows, ignore_index=True)
        except Exception:
            pass
    if df_final.empty:
        spot = spot or 28.54
        fonte = 'Modo Offline / Fim de Semana (Dados Simulados)'
        strikes_fb = np.arange(round(spot*0.88), round(spot*1.12)+0.5, 0.5)
        exps_fb = [(datetime.datetime.now() + datetime.timedelta(days=(4 - datetime.datetime.now().weekday()) % 7 + 7*w)).strftime('%y-%m-%d') for w in range(10)]
        fb_rows = []
        for ex in exps_fb:
            for k in strikes_fb:
                for is_c in [True, False]:
                    dist = abs(k - spot) / spot
                    oi = max(100, int(4500 * np.exp(-35 * dist**2)))
                    vol = int(oi * 0.35)
                    d, g, v = greeks_bs(spot, k, 0.08, 0.045, 0.28, is_c)
                    sv = 1.0 if is_c else -1.0
                    fb_rows.append({'strike': float(k), 'is_c': is_c, 'openInterest': float(oi), 'volume': float(vol), 'gamma': float(g), 'delta': float(d), 'iv': 0.28, 'exp': ex, 'gex_oi': sv*g*oi*100*spot**2*0.01, 'gex_vol': sv*g*vol*100*spot**2*0.01, 'dex_oi': d*oi*100*spot, 'dex_vol': d*vol*100*spot, 'van_oi': v*oi*100*spot})
        df_final = pd.DataFrame(fb_rows)
    return spot, df_final, fonte

@st.cache_data(ttl=600)
def load_barchart(sym):
    try:
        sess = cffi_requests.Session(impersonate='chrome124')
        sess.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', 'Accept': 'application/json, text/plain, */*', 'Referer': 'https://cboe.com'})
        url = f'https://barchart.com{sym}/options'
        sess.get(url, timeout=8)
        xsrf = sess.cookies.get('XSRF-TOKEN')
        if not xsrf: return None
        hdr = {'x-xsrf-token': urllib.parse.unquote(xsrf), 'referer': url, 'accept': 'application/json'}
        r = sess.get(f'https://barchart.com{sym}&fields=impliedVolatilityRank1y,putCallVolumeRatio,putCallOpenInterestRatio&raw=1', headers=hdr, timeout=8)
        if r.status_code == 200:
            return r.json().get('data', [{}]).get('raw', {})
    except Exception:
        return None
    return None
spot, df_all, fonte_dados = load_chain(ticker)
bc_info = load_barchart(ticker)
all_exps = sorted(df_all['exp'].unique())
c_f1, c_f2 = st.columns([1.2, 2.0])
hor_opt = c_f1.selectbox('Horizonte de Vencimentos', ['8 Semanais (~2 Meses)', 'Todos ate 3+ Meses (Padrao)', 'Toda a Cadeia Disponivel'], index=1)
def_exps = all_exps[:8] if '8 Semanais' in hor_opt else (all_exps[:14] if '3+ Meses' in hor_opt else all_exps)
sel_exps = c_f2.multiselect('Vencimentos Ativos no Calculo (YY-MM-DD)', options=all_exps, default=def_exps)
df = df_all[df_all['exp'].isin(sel_exps)].copy() if sel_exps else df_all.copy()

df_sub = df[(df['strike']>=spot*0.88) & (df['strike']<=spot*1.12)].copy()
grp = df.groupby('strike').agg(gex=('gex_oi','sum'), dex=('dex_oi','sum'), van=('van_oi','sum'), oi=('openInterest','sum'), vol=('volume','sum')).reset_index().sort_values('strike')
cg = df[df['is_c']].groupby('strike').agg(gex=('gex_oi','sum'), oi=('openInterest','sum')).reset_index()
pg = df[~df['is_c']].groupby('strike').agg(gex=('gex_oi','sum'), oi=('openInterest','sum')).reset_index()
cw, pw, vn, mv = cg.loc[cg['gex'].idxmax()], pg.loc[pg['gex'].idxmin()], grp.loc[grp['van'].idxmax()], grp.loc[grp['vol'].idxmax()]
gf, dfp = spot, spot
ns = grp[(grp['strike']>=spot*0.85) & (grp['strike']<=spot*1.15)].reset_index(drop=True)
for i in range(len(ns)-1):
    if ns.loc[i,'gex']*ns.loc[i+1,'gex'] < 0:
        gf = ns.loc[i,'strike'] - ns.loc[i,'gex']*(ns.loc[i+1,'strike']-ns.loc[i,'strike'])/(ns.loc[i+1,'gex']-ns.loc[i,'gex']); break
for i in range(len(ns)-1):
    if ns.loc[i,'dex']*ns.loc[i+1,'dex'] < 0:
        dfp = ns.loc[i,'strike'] - ns.loc[i,'dex']*(ns.loc[i+1,'strike']-ns.loc[i,'strike'])/(ns.loc[i+1,'dex']-ns.loc[i,'dex']); break

c_oi_tot = df[df['is_c']]['openInterest'].sum()
p_oi_tot = df[~df['is_c']]['openInterest'].sum()
pc_cboe = round(p_oi_tot / max(c_oi_tot, 1), 2)
strikes_mp = sorted(df_sub['strike'].unique())
mp_pain = [(k, (df_sub[df_sub['is_c']].apply(lambda r: max(0, k-r['strike'])*r['openInterest'], axis=1).sum() + df_sub[~df_sub['is_c']].apply(lambda r: max(0, r['strike']-k)*r['openInterest'], axis=1).sum())) for k in strikes_mp]
max_pain = min(mp_pain, key=lambda x: x[1])[0] if mp_pain else spot

bc_txt = f'Barchart P/C: {bc_info.get("putCallOpenInterestRatio", pc_cboe)} | IV Rank: {bc_info.get("impliedVolatilityRank1y", "N/D")}%' if bc_info else f'CBOE P/C OI: {pc_cboe} (Barchart em espera)'
st.markdown(f'<div style="background:#0c1c26;border:1px solid #00e676;border-radius:8px;padding:10px 14px;margin-bottom:12px;color:#ffffff;font-size:13px;"><b>🛡️ CONFLUENCIA DE DADOS:</b> {fonte_dados} &nbsp;|&nbsp; <b>Max Pain:</b> ${max_pain:.2f} &nbsp;|&nbsp; <b>Validacao:</b> {bc_txt}</div>', unsafe_allow_html=True)

net_gex, net_dex = grp['gex'].sum(), grp['dex'].sum()
card_html = lambda tit, val, sub, bg_pill: f'<div style="background:#0d1922;border:1px solid #234052;border-radius:10px;padding:16px;"><div style="color:#ffffff;font-size:13px;font-weight:700;margin-bottom:6px;">{tit}</div><div style="color:#ffffff;font-size:26px;font-weight:800;margin-bottom:8px;">{val}</div><span style="background:{bg_pill};color:#000000;font-size:12px;font-weight:700;padding:3px 10px;border-radius:12px;">{sub}</span></div>'
m1, m2, m3 = st.columns(3)
m1.markdown(card_html('MM (GAMMA)', 'MM LONG (Estabiliza)' if net_gex>=0 else 'MM SHORT (Acelera)', f'GEX Liquido: ${net_gex/1e6:.1f}M', '#00e676' if net_gex>=0 else '#ff5252'), unsafe_allow_html=True)
m2.markdown(card_html('FLUXO (DELTA)', 'ALTISTA (Compra)' if net_dex>=0 else 'BAIXISTA (Venda)', f'DEX Liquido: ${net_dex/1e6:.1f}M', '#00e676' if net_dex>=0 else '#ff5252'), unsafe_allow_html=True)
m3.markdown(card_html(f'SPOT {ticker}', f'${spot:.2f}', f'Gamma Flip: ${gf:.2f} | Max Pain: ${max_pain:.2f}', '#80d8ff'), unsafe_allow_html=True)

c_tv1, c_tv2, c_tv3 = st.columns([3, 1, 1])
c_tv1.markdown('#### 📈 GRAFICO AO VIVO COM NIVEIS (TEMPO REAL)')
tf_sel = c_tv2.selectbox('Timeframe', ['1m', '5m', '15m', '1h'], index=1, label_visibility='collapsed')
live_on = c_tv3.toggle('Auto-Atualizar (5m)', value=True)

@st.fragment(run_every=300 if live_on else None)
def live_chart_box():
    per = '1d' if tf_sel in ['1m', '5m'] else '5d'
    intraday = yf.Ticker(ticker).history(period=per, interval=tf_sel).reset_index()
    if intraday.empty:
        st.warning('Aguardando dados do pregao...')
        return
    time_col = 'Datetime' if 'Datetime' in intraday.columns else 'Date'
    candles = [{'time': int(pd.Timestamp(r[time_col]).timestamp()), 'open': float(r['Open']), 'high': float(r['High']), 'low': float(r['Low']), 'close': float(r['Close'])} for _, r in intraday.iterrows()]
    last_px = candles[-1]['close']
    lvls_chart = [
        {'price': float(cw.strike), 'color': '#ff1744', 'lineWidth': 2, 'lineStyle': 0, 'axisLabelVisible': True, 'title': f'Call Wall ({cw.strike:.2f})'},
        {'price': float(max_pain), 'color': '#ffd600', 'lineWidth': 1, 'lineStyle': 2, 'axisLabelVisible': True, 'title': f'Max Pain ({max_pain:.2f})'},
        {'price': float(dfp), 'color': '#ba68c8', 'lineWidth': 1, 'lineStyle': 2, 'axisLabelVisible': True, 'title': f'Delta Flip ({dfp:.2f})'},
        {'price': float(gf), 'color': '#9c27b0', 'lineWidth': 2, 'lineStyle': 0, 'axisLabelVisible': True, 'title': f'Gamma Flip ({gf:.2f})'},
        {'price': float(pw.strike), 'color': '#29b6f6', 'lineWidth': 2, 'lineStyle': 0, 'axisLabelVisible': True, 'title': f'Put Wall ({pw.strike:.2f})'}
    ]
    chartOptions = {'height': 420, 'layout': {'background': {'type': 'solid', 'color': '#070d12'}, 'textColor': '#ffffff'}, 'grid': {'vertLines': {'color': '#132533'}, 'horzLines': {'color': '#132533'}}, 'timeScale': {'timeVisible': True, 'secondsVisible': False}}
    seriesCandlestick = [{'type': 'Candlestick', 'data': candles, 'options': {'upColor': '#00e676', 'downColor': '#ff1744', 'borderVisible': False, 'wickUpColor': '#00e676', 'wickDownColor': '#ff1744'}, 'priceLines': lvls_chart}]
    st.caption(f'Ultima atualizacao: {datetime.datetime.now().strftime("%H:%M:%S")} | Ultimo Preco: ${last_px:.2f} | Fonte: {fonte_dados}')
    renderLightweightCharts([{'chart': chartOptions, 'series': seriesCandlestick}], key=f'tv_{ticker}_{tf_sel}_{int(datetime.datetime.now().timestamp())}')

live_chart_box()

st.markdown('#### 🎯 ZONAS DE IMPACTO DELTA (SUPORTE & RESISTENCIA)')
c_z = df_sub[df_sub['is_c']].groupby('strike').agg(dex=('dex_oi','sum'), oi=('openInterest','sum')).reset_index()
p_z = df_sub[~df_sub['is_c']].groupby('strike').agg(dex=('dex_oi','sum'), oi=('openInterest','sum')).reset_index()
zonas = []
for _, r in c_z[c_z['strike'] < spot].nlargest(2, 'dex').iterrows():
    zonas.append(['🟢 Suporte (Call ITM)', f'${r.strike:.2f} C', f'{r.strike-spot:+.2f}', 'MM ja comprou hedge - age como piso'])
for _, r in p_z[p_z['strike'] <= spot].nsmallest(2, 'dex').iterrows():
    zonas.append(['🟢 Suporte (Put Wall)', f'${r.strike:.2f} P', f'{r.strike-spot:+.2f}', 'MM compra na queda para neutralizar delta'])
for _, r in c_z[c_z['strike'] > spot].nlargest(2, 'dex').iterrows():
    zonas.append(['🔴 Resistencia (Call)', f'${r.strike:.2f} C', f'{r.strike-spot:+.2f}', 'MM vende no rali - barreira de alta'])
if zonas:
    df_z = pd.DataFrame(zonas, columns=['TIPO', 'STRIKE', 'DIST', 'COMPORTAMENTO DO MARKET MAKER'])
    st.markdown(df_z.to_html(index=False, classes='tbl-gama'), unsafe_allow_html=True)

st.markdown('#### 🔥 MOMENTUM REAL - VOL/OI RATIO (URGENCIA DO FLUXO POR STRIKE)')
c_vo = df_sub[df_sub['is_c']].groupby('strike').agg(v=('volume','sum'), o=('openInterest','sum')).reset_index()
p_vo = df_sub[~df_sub['is_c']].groupby('strike').agg(v=('volume','sum'), o=('openInterest','sum')).reset_index()
c_vo['ratio'] = c_vo['v'] / np.maximum(c_vo['o'], 1)
p_vo['ratio'] = p_vo['v'] / np.maximum(p_vo['o'], 1)
fig_vo = go.Figure()
fig_vo.add_trace(go.Bar(x=c_vo['strike'], y=c_vo['ratio'], name='CALL Vol/OI', marker_color='#ff1744', hovertemplate='<b>CALL Vol/OI</b><br>Strike: $%{x:.2f}<br>Ratio: %{y:.2f}x<extra></extra>'))
fig_vo.add_trace(go.Bar(x=p_vo['strike'], y=p_vo['ratio'], name='PUT Vol/OI', marker_color='#00e676', hovertemplate='<b>PUT Vol/OI</b><br>Strike: $%{x:.2f}<br>Ratio: %{y:.2f}x<extra></extra>'))
fig_vo.add_hline(y=2.5, line_dash='dot', line_color='#ffd600', annotation_text='ELEVADO (2.5x)', annotation_font_color='#ffd600')
fig_vo.add_hline(y=7.8, line_dash='dot', line_color='#ff5252', annotation_text='ALERTA MAX (7.8x)', annotation_font_color='#ff5252')
fig_vo.update_layout(height=280, barmode='group', paper_bgcolor='#0c161e', plot_bgcolor='#070d12', font_color='#ffffff', legend=dict(font=dict(color='#ffffff')), margin=dict(l=10,r=10,t=25,b=15))
st.plotly_chart(fig_vo, width='stretch')

st.markdown('#### 📅 ESTRUTURA DE VENCIMENTOS (CURTO PRAZO • SEMANAIS • MENSAIS)')
def is_monthly_opex(exp_yymmdd):
    dt = datetime.datetime.strptime('20' + exp_yymmdd, '%Y-%m-%d')
    return dt.weekday() == 4 and 15 <= dt.day <= 21

def plot_oi_bucket(col_obj, sub_df, titulo_box):
    with col_obj:
        if sub_df.empty:
            st.info(f'{titulo_box}: Sem dados disponiveis')
            return
        c_e = sub_df[sub_df['is_c']].groupby('strike')['openInterest'].sum().reset_index()
        p_e = sub_df[~sub_df['is_c']].groupby('strike')['openInterest'].sum().reset_index()
        fg = go.Figure()
        fg.add_trace(go.Bar(x=c_e['strike'], y=c_e['openInterest'], name='CALL OI (Resistencia)', marker_color='#ff1744', hovertemplate='<b>CALL OI (Resistencia)</b><br>Strike: $%{x:.2f}<br>Contratos: %{y:,.0f}<br>Acao MM: Barreira / Venda no Rali<extra></extra>'))
        fg.add_trace(go.Bar(x=p_e['strike'], y=p_e['openInterest'], name='PUT OI (Suporte)', marker_color='#00e676', hovertemplate='<b>PUT OI (Suporte)</b><br>Strike: $%{x:.2f}<br>Contratos: %{y:,.0f}<br>Acao MM: Suporte / Compra na Queda<extra></extra>'))
        fg.add_vline(x=spot, line_dash='dot', line_color='#80d8ff', annotation_text=f'SPOT {spot:.2f}', annotation_font_color='#ffffff')
        fg.update_layout(title=dict(text=titulo_box, font=dict(color='#ffffff', size=13)), legend=dict(font=dict(color='#ffffff')), height=250, barmode='group', paper_bgcolor='#0c161e', plot_bgcolor='#070d12', font=dict(color='#ffffff'), margin=dict(l=10,r=10,t=40,b=15))
        st.plotly_chart(fg, width='stretch')

exps_disp = sorted(df_all['exp'].unique())
exp_1, exp_2 = exps_disp[:1], exps_disp[1:2]
semanais_fut = [e for e in exps_disp[2:] if not is_monthly_opex(e) and (datetime.datetime.strptime('20'+e,'%Y-%m-%d') - datetime.datetime.now()).days <= 65]
mensais_lista = [e for e in exps_disp if is_monthly_opex(e)]
mensal_1 = mensais_lista[:1]
meses_frente = [e for e in exps_disp if e not in exp_1 and e not in exp_2 and e not in semanais_fut and e not in mensal_1]

r1_c1, r1_c2 = st.columns(2)
plot_oi_bucket(r1_c1, df_all[(df_all['exp'].isin(exp_1)) & (df_all['strike']>=spot*0.88) & (df_all['strike']<=spot*1.12)], f'1. Vencimento Mais Proximo ({exp_1[0] if exp_1 else "N/D"})')
plot_oi_bucket(r1_c2, df_all[(df_all['exp'].isin(exp_2)) & (df_all['strike']>=spot*0.88) & (df_all['strike']<=spot*1.12)], f'2. Proxima Semana ({exp_2[0] if exp_2 else "N/D"})')
plot_oi_bucket(st.container(), df_all[(df_all['exp'].isin(semanais_fut)) & (df_all['strike']>=spot*0.88) & (df_all['strike']<=spot*1.12)], f'3. Proximos Vencimentos Semanais Futuros ({len(semanais_fut)} datas)')
r3_c1, r3_c2 = st.columns(2)
plot_oi_bucket(r3_c1, df_all[(df_all['exp'].isin(mensal_1)) & (df_all['strike']>=spot*0.88) & (df_all['strike']<=spot*1.12)], f'4. Vencimento Mensal OPEX ({mensal_1[0] if mensal_1 else "N/D"})')
plot_oi_bucket(r3_c2, df_all[(df_all['exp'].isin(meses_frente)) & (df_all['strike']>=spot*0.88) & (df_all['strike']<=spot*1.12)], f'5. Meses a Frente ({len(meses_frente)} vencimentos)')

st.markdown('#### 🧩 MATRIZES STRIKE × VENCIMENTO (OI WALLS & GEX POR DATA)')
exps_mat = sorted(df_sub['exp'].unique())[:5]
df_mat = df_sub[df_sub['exp'].isin(exps_mat)].copy()
m_col1, m_col2 = st.columns(2)

with m_col1:
    st.markdown('**OI Walls (Dominancia Call vs Put)**')
    piv_c = df_mat[df_mat['is_c']].pivot_table(index='strike', columns='exp', values='openInterest', aggfunc='sum', fill_value=0)
    piv_p = df_mat[~df_mat['is_c']].pivot_table(index='strike', columns='exp', values='openInterest', aggfunc='sum', fill_value=0)
    all_k_mat = sorted(df_mat['strike'].unique(), reverse=True)
    rows_oi = []
    for k in all_k_mat:
        row_dict = {'Strike': f'${k:.2f}'}
        for e in exps_mat:
            vc_val = piv_c.loc[k, e] if (k in piv_c.index and e in piv_c.columns) else 0
            vp_val = piv_p.loc[k, e] if (k in piv_p.index and e in piv_p.columns) else 0
            if vc_val == 0 and vp_val == 0:
                row_dict[e] = '-'
            elif vc_val >= vp_val:
                row_dict[e] = f'C {vc_val/1e3:.1f}K' if vc_val >= 1000 else f'C {int(vc_val)}'
            else:
                row_dict[e] = f'P {vp_val/1e3:.1f}K' if vp_val >= 1000 else f'P {int(vp_val)}'
        rows_oi.append(row_dict)
    df_oi_html = pd.DataFrame(rows_oi)
    st.markdown(df_oi_html.to_html(index=False, classes='tbl-gama'), unsafe_allow_html=True)

with m_col2:
    st.markdown('**GEX por Vencimento (Exposicao Liquida)**')
    piv_g = df_mat.pivot_table(index='strike', columns='exp', values='gex_oi', aggfunc='sum', fill_value=0)
    rows_gex = []
    for k in all_k_mat:
        row_dict = {'Strike': f'${k:.2f}'}
        for e in exps_mat:
            gv = piv_g.loc[k, e] if (k in piv_g.index and e in piv_g.columns) else 0
            if abs(gv) < 100:
                row_dict[e] = '-'
            elif abs(gv) >= 1e6:
                row_dict[e] = f'{gv/1e6:+.2f}M'
            else:
                row_dict[e] = f'{gv/1e3:+.1f}K'
        rows_gex.append(row_dict)
    df_gex_html = pd.DataFrame(rows_gex)
    st.markdown(df_gex_html.to_html(index=False, classes='tbl-gama'), unsafe_allow_html=True)

st.markdown('#### 🤖 REGIME CTA & PROJECAO DE GATILHOS (BUY / SELL STOPS)')
hist_cta = yf.Ticker(ticker).history(period='1y')['Close'].dropna()
rets = np.log(hist_cta / hist_cta.shift(1)).dropna()
vol_real = float(rets.tail(21).std() * np.sqrt(252) * 100)
wins = [5, 10, 15, 20, 30, 40, 50, 60, 90, 120, 150, 200]
long_cnt = sum([1 for w in wins if spot > float(hist_cta.rolling(w).mean().iloc[-1])])
pos_score = round((long_cnt / len(wins)) * 2 - 1, 2)

ct1, ct2, ct3, ct4 = st.columns(4)
ct1.markdown(card_html('REGIME CTA', 'LONG' if pos_score >= 0 else 'SHORT', f'{long_cnt}/12 janelas long', '#00e676' if pos_score >= 0 else '#ff5252'), unsafe_allow_html=True)
ct2.markdown(card_html('POSITIONING', f'{pos_score:+.2f}', 'Escala -1.0 a +1.0', '#80d8ff'), unsafe_allow_html=True)
ct3.markdown(card_html('VOL REALIZADA', f'{vol_real:.1f}%', 'Anualizada (21d)', '#ffd600'), unsafe_allow_html=True)
ct4.markdown(card_html('SPOT ATUAL', f'${spot:.2f}', ticker, '#ce93d8'), unsafe_allow_html=True)

np.random.seed(42)
dt = 1/252
mu, sig_d = float(rets.tail(60).mean()*252), vol_real/100
sims = spot * np.exp(np.cumsum((mu - 0.5*sig_d**2)*dt + sig_d*np.sqrt(dt)*np.random.randn(20, 500), axis=0))
p90, p50, p10 = np.percentile(sims, 90, axis=1), np.percentile(sims, 50, axis=1), np.percentile(sims, 10, axis=1)
h_tail = hist_cta.tail(45)
x_hist, x_fut = list(range(-len(h_tail)+1, 1)), list(range(0, 21))

fig_cta = go.Figure()
fig_cta.add_trace(go.Scatter(x=x_hist, y=h_tail.values, name='Historico', line=dict(color='#7986cb', width=2)))
fig_cta.add_trace(go.Scatter(x=x_fut, y=np.insert(p90, 0, spot), name='Bull (p90)', line=dict(color='#00e676', dash='dot')))
fig_cta.add_trace(go.Scatter(x=x_fut, y=np.insert(p50, 0, spot), name='Median (p50)', line=dict(color='#ffd600', width=2)))
fig_cta.add_trace(go.Scatter(x=x_fut, y=np.insert(p10, 0, spot), name='Bear (p10)', line=dict(color='#ff1744', dash='dot'), fill='tonexty', fillcolor='rgba(0,230,118,0.06)'))

for w_b in [20, 60, 120]:
    lvl = float(hist_cta.tail(w_b).max())
    if lvl > spot:
        fig_cta.add_hline(y=lvl, line_dash='dash', line_color='#00e676', annotation_text=f'Buy Stop w{w_b}: ${lvl:.2f} ({(lvl/spot-1)*100:+.1f}%)', annotation_font_color='#00e676')
for w_s in [20, 60, 120]:
    lvl = float(hist_cta.tail(w_s).min())
    if lvl < spot:
        fig_cta.add_hline(y=lvl, line_dash='dash', line_color='#ff1744', annotation_text=f'Sell Stop w{w_s}: ${lvl:.2f} ({(lvl/spot-1)*100:+.1f}%)', annotation_font_color='#ff5252')

fig_cta.update_layout(height=360, paper_bgcolor='#0c161e', plot_bgcolor='#070d12', font_color='#ffffff', legend=dict(font=dict(color='#ffffff')), margin=dict(l=10,r=10,t=25,b=15))
st.plotly_chart(fig_cta, width='stretch')


st.markdown('---')
st.markdown('### 🇧🇷 PAINEL WIN AGREGADO - CONVERSAO EWZ -> MINI-INDICE (B3)')
c_w1, c_w2, c_w3 = st.columns([1.2, 1.2, 1.6])
bvsp_px = 167605.0
fonte_win = 'Estimativa WINFUT (IBOV + Premio DI)'
try:
    ibov_now = float(yf.Ticker('^BVSP').history(period='5d')['Close'].dropna().iloc[-1])
    bvsp_px = round((ibov_now * (167605.0 / 166376.43)) / 5) * 5
except Exception:
    pass
win_spot = c_w1.number_input('Cotacao Atual WIN (Pts)', value=float(bvsp_px), step=50.0)
fator_win = win_spot / spot
c_w2.markdown(card_html('SPOT WIN EQUIVALENTE', f'{win_spot:,.0f} pts', f'{fonte_win} - Fator: {fator_win:,.1f}', '#00e676'), unsafe_allow_html=True)
c_w3.info(f'Gamma Flip WIN: {gf * fator_win:,.0f} pts | Call Wall WIN: {cw.strike * fator_win:,.0f} pts | Put Wall WIN: {pw.strike * fator_win:,.0f} pts')

sub_w = grp[(grp['strike']>=spot*0.88) & (grp['strike']<=spot*1.12)].copy()
sub_w['win_pts'] = (sub_w['strike'] * fator_win / 5).round() * 5
sub_w['y_lbl'] = sub_w.apply(lambda r: f"{int(r['win_pts']):,}  (${r['strike']:.2f})", axis=1)
vol_g = df_sub.groupby('strike').agg(gex_v=('gex_vol','sum'), dex_v=('dex_vol','sum'), oi_tot=('openInterest','sum'), vol_tot=('volume','sum')).reset_index()
sub_w = pd.merge(sub_w, vol_g, on='strike', how='left').fillna(0)
sub_w['van_v'] = sub_w['van'] * (sub_w['vol_tot'] / np.maximum(sub_w['oi_tot'], 1))

fig_w = make_subplots(rows=1, cols=3, shared_yaxes=True, subplot_titles=('DELTA FLOW (DEX) • OI + Vol', 'EXPOSICAO GAMA (GEX) • OI + Vol', 'VANNA (dΔ/dVol) • OI + Vol'))
fmt_n = lambda a: [f'{x/1e6:+.1f}M' if abs(x)>=1e6 else (f'{x/1e3:+.0f}k' if abs(x)>=1e3 else '') for x in a]

def add_dual_col(col_idx, oi_s, vol_s, c_oi_pos, c_oi_neg, c_v_pos, c_v_neg):
    mx = max(oi_s.abs().max(), vol_s.abs().max(), 1e5)
    oi_plot = []
    t_vol_list, x_vol_txt, pos_vol_txt = [], [], []
    for vo, vv in zip(oi_s, vol_s):
        if abs(vo) > 0 and abs(vv) > 0 and (vo * vv > 0) and abs(vo) < abs(vv) * 1.45:
            vo_vis = np.sign(vo) * max(abs(vo), abs(vv) + 0.32 * mx)
        else:
            vo_vis = vo
        oi_plot.append(vo_vis / 1e6)
        lbl_v = f'{vv/1e6:+.1f}M' if abs(vv)>=1e6 else (f'{vv/1e3:+.0f}k' if abs(vv)>=1e3 else '')
        t_vol_list.append(lbl_v)
        if lbl_v:
            if (vo * vv > 0) and abs(vo_vis - vv) < 0.30 * mx:
                x_vol_txt.append(-0.04 * (mx/1e6) if vv >= 0 else 0.04 * (mx/1e6))
                pos_vol_txt.append('middle left' if vv >= 0 else 'middle right')
            else:
                x_vol_txt.append(vv / 1e6)
                pos_vol_txt.append('middle right' if vv >= 0 else 'middle left')
        else:
            x_vol_txt.append(0)
            pos_vol_txt.append('middle right')
    fig_w.add_trace(go.Bar(y=sub_w['win_pts'], x=oi_plot, orientation='h', marker_color=[c_oi_pos if x>=0 else c_oi_neg for x in oi_s], text=fmt_n(oi_s), textposition='outside', cliponaxis=False, textfont=dict(color='#cfd8dc', size=10), customdata=oi_s/1e6, hovertemplate='%{y}<br>OI Real: %{customdata:+.2f}M<extra></extra>'), 1, col_idx)
    fig_w.add_trace(go.Bar(y=sub_w['win_pts'], x=vol_s/1e6, orientation='h', width=0.45, marker_color=[c_v_pos if x>=0 else c_v_neg for x in vol_s], hovertemplate='%{y}<br>Fluxo Vol: %{x:+.2f}M<extra></extra>'), 1, col_idx)
    fig_w.add_trace(go.Scatter(y=sub_w['win_pts'], x=x_vol_txt, text=t_vol_list, mode='text', textposition=pos_vol_txt, textfont=dict(color='#ffd600', size=10), cliponaxis=False, hoverinfo='skip'), 1, col_idx)
    lim = (mx / 1e6) * 1.55
    fig_w.update_xaxes(range=[-lim, lim], row=1, col=col_idx)

add_dual_col(1, sub_w['dex'], sub_w['dex_v'], 'rgba(0,230,118,0.28)', 'rgba(255,87,34,0.28)', '#00e676', '#ff5722')
add_dual_col(2, sub_w['gex'], sub_w['gex_v'], 'rgba(156,39,176,0.32)', 'rgba(255,87,34,0.32)', '#ab47bc', '#ff7043')
add_dual_col(3, sub_w['van'], sub_w['van_v'], 'rgba(0,230,118,0.28)', 'rgba(255,23,68,0.28)', '#00e676', '#ff1744')
fig_w.update_yaxes(tickmode='array', tickvals=sub_w['win_pts'], ticktext=sub_w['y_lbl'], row=1, col=1)
fig_w.add_hline(y=win_spot, line_dash='dash', line_color='#00e5ff', line_width=2, annotation_text=f'  PRECO ATUAL WIN: {win_spot:,.0f} pts', annotation_position='top left', annotation_font=dict(color='#00e5ff', size=11))
fig_w.update_layout(barmode='overlay', height=600, paper_bgcolor='#070d12', plot_bgcolor='#0b141c', font_color='#ffffff', showlegend=False, margin=dict(l=15,r=25,t=40,b=15))
st.plotly_chart(fig_w, width='stretch')

l1, l2, l3 = st.columns(3)
l1.markdown('<div style="background:#0c161e;border:1px solid #00e676;border-radius:8px;padding:12px;font-size:12px;line-height:1.45;"><b style="color:#00e676;">▲ DELTA FLOW (DEX) - AÇÃO DO MM</b><br>• <b>Barra Verde (+):</b><br>&nbsp;&nbsp;↗ <i>Preço Subindo:</i> <b>MM vende na alta</b> (Resistencia/Freio).<br>&nbsp;&nbsp;↘ <i>Preço Caindo:</i> <b>MM recompra hedge</b> (Alivia queda).<br>• <b>Barra Laranja (-):</b><br>&nbsp;&nbsp;↗ <i>Preço Subindo:</i> <b>MM encerra vendas</b> (Ajuda repique).<br>&nbsp;&nbsp;↘ <i>Preço Caindo:</i> <b>MM vende mais</b> (Empurra ate suporte).<br><span style="color:#90a4ae;font-size:11px;">Solida = Fluxo do dia | Translucida = OI acumulado</span></div>', unsafe_allow_html=True)
l2.markdown('<div style="background:#0c161e;border:1px solid #ab47bc;border-radius:8px;padding:12px;font-size:12px;line-height:1.45;"><b style="color:#ce93d8;">◆ EXPOSICAO GAMA (GEX) - AÇÃO DO MM</b><br>• <b>Roxo (+ Long Gamma - Freio):</b><br>&nbsp;&nbsp;↗ <i>Preço Subindo:</i> <b>MM vende repiques</b> (Trava rali).<br>&nbsp;&nbsp;↘ <i>Preço Caindo:</i> <b>MM compra quedas</b> (Segura fundo).<br>• <b>Laranja (- Short Gamma - Acelerador):</b><br>&nbsp;&nbsp;↗ <i>Preço Subindo:</i> <b>MM compra na alta</b> (Acelera rompimento).<br>&nbsp;&nbsp;↘ <i>Preço Caindo:</i> <b>MM vende na queda</b> (Acelera queda).<br><span style="color:#90a4ae;font-size:11px;">Gamma Flip (Zero) = Virada de freio para acelerador</span></div>', unsafe_allow_html=True)
l3.markdown('<div style="background:#0c161e;border:1px solid #ffd600;border-radius:8px;padding:12px;font-size:12px;line-height:1.45;"><b style="color:#ffd600;">⚡ VANNA (dΔ/dIV) - AÇÃO DO MM</b><br>• <b>Verde (+ Vanna Positiva):</b><br>&nbsp;&nbsp;↗ <i>Preço Subindo (IV cai):</i> <b>MM compra o ativo</b> (Sustenta alta).<br>&nbsp;&nbsp;↘ <i>Preço Caindo (IV sobe):</i> <b>MM vende o ativo</b> (Agrava queda).<br>• <b>Vermelho (- Vanna Negativa):</b><br>&nbsp;&nbsp;↗ <i>Preço Subindo (IV cai):</i> <b>MM vende o ativo</b> (Segura alta).<br>&nbsp;&nbsp;↘ <i>Preço Caindo (IV sobe):</i> <b>MM compra o ativo</b> (Estanca queda).<br><span style="color:#90a4ae;font-size:11px;">Crítico em aberturas, noticias e decisoes de juros</span></div>', unsafe_allow_html=True)
st.markdown('---')

from geradores import render_geradores
render_geradores(spot, win_spot, df_sub, cw, pw, vn, dfp, gf)
