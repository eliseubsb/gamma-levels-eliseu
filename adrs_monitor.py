import streamlit as st
import pandas as pd
import re
from datetime import datetime
from curl_cffi import requests as cffi_requests
import yfinance as yf

@st.cache_data(ttl=60)
def fetch_macro_all():
    out = {}
    for nome, tk in [('VIX','^VIX'),('SPY','SPY'),('BRENT','BZ=F'),('USDBRL','USDBRL=X')]:
        try:
            h = yf.Ticker(tk).history(period='5d')['Close'].dropna()
            if len(h) >= 2:
                px, prev = float(h.iloc[-1]), float(h.iloc[-2])
                out[nome] = (px, ((px - prev) / prev) * 100.0)
            elif len(h) == 1:
                out[nome] = (float(h.iloc[-1]), 0.0)
        except Exception:
            out[nome] = (0.0, 0.0)
    return out

@st.cache_data(ttl=120)
def fetch_cboe_full(sym):
    sess = cffi_requests.Session(impersonate='chrome124')
    sess.headers.update({'User-Agent':'Mozilla/5.0','Accept':'application/json','Referer':'https://cboe.com'})
    spot, chg, rows = 0.0, 0.0, []
    try:
        h = yf.Ticker(sym).history(period='5d')['Close'].dropna()
        if len(h) >= 2:
            spot, prev = float(h.iloc[-1]), float(h.iloc[-2])
            chg = ((spot - prev) / prev) * 100.0
        elif len(h) == 1:
            spot = float(h.iloc[-1])
    except Exception:
        pass
    try:
        r = sess.get(f'https://cdn.cboe.com/api/global/delayed_quotes/options/{sym.replace(chr(45),chr(46))}.json', timeout=6)
        if r.status_code == 200:
            raw = r.json().get('data', {})
            if raw.get('current_price'): spot = float(raw.get('current_price'))
            pat = re.compile(r'^[A-Z\.]+(\d{6})([CP])(\d{8})$')
            for o in raw.get('options', []):
                m = pat.match(o.get('option', ''))
                if not m: continue
                exp_s, cp, k_raw = m.groups()
                try:
                    dias_v = (datetime.strptime(exp_s, '%y%m%d').date() - datetime.now().date()).days
                    if dias_v < 0 or dias_v > 42: continue
                except Exception:
                    pass
                oi = float(o.get('open_interest') or 0)
                if oi <= 0: continue
                k = int(k_raw) / 1000.0
                g, d = float(o.get('gamma') or 0), float(o.get('delta') or 0)
                is_c = (cp == 'C')
                rows.append({'strike':k,'is_c':is_c,'oi':oi,'d_v':dias_v,'gex':(1.0 if is_c else -1.0)*g*oi*100*(spot**2)*0.01,'dex':d*oi*100*spot})
    except Exception:
        pass
    if not rows or spot <= 0:
        return {'ok':False,'spot':spot,'chg':chg,'gex':0.0,'dex':0.0,'cw':spot,'cw_oi':0,'pw':spot,'pw_oi':0,'gf':spot,'dfp':spot,'oi_c':0,'oi_p':0,'df4w':[]}
    df = pd.DataFrame(rows)
    df = df[(df['strike'] >= spot*0.75) & (df['strike'] <= spot*1.25)]
    calls, puts = df[df['is_c']], df[~df['is_c']]
    cw_r = calls.groupby('strike')['oi'].sum().reset_index().sort_values('oi', ascending=False).iloc[0] if not calls.empty else None
    pw_r = puts.groupby('strike')['oi'].sum().reset_index().sort_values('oi', ascending=False).iloc[0] if not puts.empty else None
    grp = df.groupby('strike').agg(gex=('gex','sum'), dex=('dex','sum')).reset_index().sort_values('strike')
    gf, dfp = spot, spot
    for i in range(len(grp)-1):
        if grp.iloc[i]['gex'] <= 0 and grp.iloc[i+1]['gex'] > 0: gf = float(grp.iloc[i+1]['strike']); break
    for i in range(len(grp)-1):
        if grp.iloc[i]['dex'] >= 0 and grp.iloc[i+1]['dex'] < 0: dfp = float(grp.iloc[i+1]['strike']); break
    return {'ok':True,'spot':spot,'chg':chg,'gex':float(df['gex'].sum()),'dex':float(df['dex'].sum()),'cw':float(cw_r['strike']) if cw_r is not None else spot,'cw_oi':int(cw_r['oi']) if cw_r is not None else 0,'pw':float(pw_r['strike']) if pw_r is not None else spot,'pw_oi':int(pw_r['oi']) if pw_r is not None else 0,'gf':gf,'dfp':dfp,'oi_c':int(calls['oi'].sum()),'oi_p':int(puts['oi'].sum())}

def render_adrs_blocos(win_spot, filtro_bloco=None):
    macro = fetch_macro_all()
    spy = fetch_cboe_full('SPY')
    fin_cfg = [('ITUB','Itau',8.0),('NU','Nubank',7.5),('BBD','Bradesco',3.5)]
    com_cfg = [('VALE','Vale',12.0),('PBR','Petro ON',7.0),('PBR-A','Petro PN',5.0)]
    fmt_m = lambda v: f'{v/1e6:+.1f}M' if abs(v)>=1e6 else f'{v/1e3:+.0f}k'
    st.markdown('---')
    st.subheader('🌍 BLOCO 1 - RADAR MACRO GLOBAL (VIX • S&P 500 • BRENT • DOLAR)')
    m1, m2, m3, m4 = st.columns(4)
    for col_m, lbl, km, pref, inv in [(m1,'⚡ VIX','VIX','',True),(m2,'🇺🇸 S&P 500 (SPY)','SPY','$',False),(m3,'🛢️ BRENT','BRENT','$',False),(m4,'💵 DOLAR','USDBRL','R$ ',True)]:
        px_m, ch_m = macro.get(km, (0.0, 0.0))
        col_m.metric(lbl, f'{pref}{px_m:.2f}', f'{ch_m:+.2f}%', delta_color='inverse' if inv else 'normal')
    if spy['ok']:
        st.info(f'🎯 S&P 500 (SPY CBOE): Call Wall ${spy["cw"]:.2f} ({int(spy["cw_oi"]/1000)}k) | Gamma Flip ${spy["gf"]:.2f} | Delta Flip ${spy["dfp"]:.2f} | Put Wall ${spy["pw"]:.2f} ({int(spy["pw_oi"]/1000)}k) | GEX {fmt_m(spy["gex"])} | DEX {fmt_m(spy["dex"])}')
    col_f, col_c = st.columns(2)
    it_fin, it_com = [], []
    pares = [(col_f, '🏦 BLOCO 2 - SETOR FINANCEIRO', fin_cfg, it_fin)] if filtro_bloco=='FINANCEIRO' else ([(col_c, '⛏️🛢️ BLOCO 3 - VALE & PETROBRAS', com_cfg, it_com)] if filtro_bloco=='COMMODITIES' else [(col_f, '🏦 BLOCO 2 - SETOR FINANCEIRO', fin_cfg, it_fin), (col_c, '⛏️🛢️ BLOCO 3 - VALE & PETROBRAS', com_cfg, it_com)])
    for col, tit, cfg, dest in pares:
        with col:
            st.subheader(tit)
            rows_t = []
            conv_w = lambda v: f'{int(round((win_spot * (v / d["spot"])) / 5.0) * 5):,}'.replace(',', '.') if d['spot'] > 0 and v > 0 else '-'
            for tk, nome, peso in cfg:
                d = fetch_cboe_full(tk)
                dest.append((tk, nome, peso, d))
                rows_t.append({'Ativo': f'{tk.replace(chr(45),chr(46))} ({nome})', 'Peso': f'{peso:.1f}%', 'Spot': f'${d["spot"]:.2f}', 'Var': f'{d["chg"]:+.2f}%', 'GEX': fmt_m(d['gex']), 'DEX': fmt_m(d['dex']), 'Call Wall': f'${d["cw"]:.2f} ({int(d["cw_oi"]/1000)}k)', 'Gamma Flip': f'${d["gf"]:.2f}', 'Put Wall': f'${d["pw"]:.2f} ({int(d["pw_oi"]/1000)}k)', 'OI C/P': f'{int(d["oi_c"]/1000)}k/{int(d["oi_p"]/1000)}k'})
                rows_t.append({'Ativo': f'↳ {nome} (WIN)', 'Peso': 'pts WIN', 'Spot': conv_w(d['spot']), 'Var': '-', 'GEX': '-', 'DEX': '-', 'Call Wall': conv_w(d['cw']), 'Gamma Flip': conv_w(d['gf']), 'Put Wall': conv_w(d['pw']), 'OI C/P': '-'})
            st.dataframe(pd.DataFrame(rows_t), width='stretch', hide_index=True)
    st.markdown('---')
    st.subheader('🎯 PAINEL DE CONFLUENCIAS & ALVOS CONVERTIDOS NO WIN (POR BLOCO + SOMA TOTAL)')
    def calc_grp(itens):
        linhas, cnt, ptot, pmov, pts_s = [], 0, 0.0, 0.0, 0.0
        for tk, nome, peso, d in itens:
            sp = d['spot']
            ptot += peso
            if sp <= 0 or not d['ok']: continue
            av = [('🔴 Call Wall', d['cw']), ('🔵 Put Wall', d['pw']), ('🟣 Gamma Flip', d['gf']), ('🟡 Delta Flip', d['dfp'])]
            av = [(l, p, abs(p-sp)/sp*100.0, p-sp) for l, p in av if p > 0]
            if not av: continue
            lbl, px_a, dist_p, diff_u = min(av, key=lambda x: x)
            spct = ((px_a - sp) / sp) * 100.0
            wa = round((win_spot * (1.0 + spct/100.0)) / 5.0) * 5
            imp = (spct / 100.0) * win_spot * (peso / 100.0)
            pts_s += imp
            if dist_p <= 3.5:
                cnt += 1
                pmov += peso
            stt = '🔥 MUITO PERTO' if dist_p <= 1.0 else ('⚡ APROXIMANDO' if dist_p <= 2.5 else '📍 EM ROTA')
            linhas.append({'Status': stt, 'Ativo': f'{tk.replace(chr(45),chr(46))} ({nome})', 'Peso': f'{peso:.1f}%', 'Spot': f'${sp:.2f}', 'Barreira': f'{lbl} ${px_a:.2f}', 'Distancia': f'{diff_u:+.2f}$ ({spct:+.2f}%)', 'Alvo WIN Equiv': f'{wa:,.0f} pts ({wa-win_spot:+.0f})', 'Impacto WIN': f'{imp:+.0f} pts', '_ord': dist_p})
        return linhas, cnt, len(itens), pmov, (pmov/ptot*100.0 if ptot>0 else 0.0), pts_s, round((win_spot+pts_s)/5.0)*5
    lf, cf_f, tf, pmf, pcf, ptsf, alvf = calc_grp(it_fin)
    lc, cf_c, tc, pmc, pcc, ptsc, alvc = calc_grp(it_com)
    p_all = sum(x[2] for x in it_fin+it_com) or 1.0
    st.markdown('<style>[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {color: #ffffff !important;} [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {color: #e0e0e0 !important;}</style>', unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    k1.metric('🏦 BLOCO FINANCEIRO', f'{cf_f}/{tf} Confluencias ({pmf:.1f}% Indice)', f'Alvo WIN: {alvf:,.0f} pts ({ptsf:+.0f})')
    k2.metric('⛏️🛢️ BLOCO COMMODITIES', f'{cf_c}/{tc} Confluencias ({pmc:.1f}% Indice)', f'Alvo WIN: {alvc:,.0f} pts ({ptsc:+.0f})')
    k3.metric('🎯 SOMA TOTAL CONFLUENCIAS', f'{cf_f+cf_c}/{tf+tc} Confluencias ({(pmf+pmc)/p_all*100:.0f}% Peso)', f'Alvo WIN: {round((win_spot+ptsf+ptsc)/5.0)*5:,.0f} pts ({ptsf+ptsc:+.0f})')
    todas_l = sorted(lf + lc, key=lambda x: x['_ord'])
    if todas_l:
        st.dataframe(pd.DataFrame(todas_l).drop(columns=['_ord']), width='stretch', hide_index=True)
    render_oi_4w_grid(win_spot, it_fin + it_com)

def render_oi_4w_grid(win_spot, itens):
    st.markdown('---')
    st.subheader('📊 OPEN INTEREST (4 SEMANAS / 28 DIAS) - OI CALL/PUT + CONVERSAO WIN POR QUADRADINHO')
    cols = st.columns(3)
    idx_c = 0
    for tk, nome, peso, d in itens:
        sp = d.get('spot', 0.0)
        recs = d.get('df4w', [])
        if sp.__le__(0) or not recs: continue
        df4 = pd.DataFrame(recs)
        df4 = df4[(df4['strike'].__ge__(sp*0.90)) & (df4['strike'].__le__(sp*1.10))]
        if df4.empty: continue
        grp = df4.groupby('strike').apply(lambda g: pd.Series({'c': g[g['is_c']]['oi'].sum(), 'p': g[~g['is_c']]['oi'].sum(), 'tot': g['oi'].sum()})).reset_index().sort_values('tot', ascending=False).head(6).sort_values('strike')
        cells = ''
        for _, r in grp.iterrows():
            k = float(r['strike'])
            c_k, p_k = int(round(r['c']/1000.0)), int(round(r['p']/1000.0))
            w_pts = int(round((win_spot * (1.0 + (k - sp)/sp)) / 5.0) * 5)
            w_fmt = f'{w_pts:,}'.replace(',', '.')
            bg = '#2b1218' if c_k > p_k else '#0e2922'
            bd = '#ff5252' if c_k > p_k else '#00e676'
            cells += f'<div style="background:{bg};border:1px solid {bd};border-radius:6px;padding:6px 4px;text-align:center;"><span style="color:#b0bec5;font-size:10px;">${k:g}</span><br><b style="color:#ff8a80;font-size:12px;">{c_k}k C</b> <span style="color:#78909c;">/</span> <b style="color:#69f0ae;font-size:12px;">{p_k}k P</b><br><b style="color:#00e5ff;font-size:11px;">{w_fmt} pts</b></div>'
        with cols[idx_c % 3]:
            st.markdown(f'<div style="background:#091118;border:1px solid #1e2d3b;border-radius:8px;padding:8px;margin-bottom:10px;"><b style="color:#ffffff;font-size:13px;">{tk.replace(chr(45),chr(46))} ({nome})</b> <span style="color:#90a4ae;font-size:11px;">Spot ${sp:.2f}</span><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:6px;">{cells}</div></div>', unsafe_allow_html=True)
        idx_c += 1
