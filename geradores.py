import streamlit as st

def render_geradores(spot, win_spot, df_sub, cw, pw, vn, dfp, gf):
    q = chr(34)
    st.markdown('---')
    st.markdown('### ⚡ CENTRAL DE EXPORTACAO - TRADINGVIEW (PINE v6) & PROFIT (NTSL)')
    st.markdown('<style>div.stButton > button {background:#0c161e !important; color:#ffffff !important; border:1px solid #00e676 !important; font-weight:600 !important; border-radius:8px !important; padding:10px 6px !important;} div.stButton > button:hover {background:#132634 !important; border-color:#ffd600 !important; color:#ffd600 !important;}</style>', unsafe_allow_html=True)
    ks = sorted(df_sub['strike'].unique())
    gcv, gpv, gcoi, gpoi, vc, vp, dcoi, dpoi, dnv = [], [], [], [], [], [], [], [], []
    for k in ks:
        sk = df_sub[df_sub['strike']==k]
        c_df, p_df = sk[sk['is_c']], sk[~sk['is_c']]
        gcv.append(float(c_df['gex_vol'].sum()))
        gpv.append(float(p_df['gex_vol'].sum()))
        gcoi.append(float(c_df['gex_oi'].sum()))
        gpoi.append(float(p_df['gex_oi'].sum()))
        vc.append(float(c_df['volume'].sum()))
        vp.append(float(p_df['volume'].sum()))
        dcoi.append(float(c_df['dex_oi'].sum()))
        dpoi.append(float(p_df['dex_oi'].sum()))
        dnv.append(float(sk['dex_vol'].sum()))
    fmt_a = lambda l: 'array.from(' + ','.join([str(round(x,2)) for x in l]) + ')' if l else 'array.new_float(0)'
    fator = win_spot / spot
    conv_pts = lambda v: int(round((v * fator) / 5.0) * 5)

    def build_pine(modo):
        q = chr(34)
        dy_pts = round(win_spot * 0.0024, 0)
        if modo == 'EWZ':
            tit, flt = 'GAMMA-LEVELS EWZ (NUMEROS)', 'str.contains(str.upper(syminfo.ticker), ' + q + 'EWZ' + q + ')'
            sc_str, cfn = 'overlay=true', 'conv(v) => v'
            dy_def, h_ab, m_ab, fstr, p_ref = '0.14', '10', '30', '#.##', str(round(spot,2))
        elif modo == 'BRA50':
            tit, flt = 'GAMMA-LEVELS BRA50 (ESCALA EWZ DIREITA)', 'str.contains(str.upper(syminfo.ticker), ' + q + 'BRA50' + q + ')'
            sc_str, cfn = 'overlay=true, scale=scale.right', 'conv(v) => v'
            dy_def, h_ab, m_ab, fstr, p_ref = '0.14', '9', '0', '#.##', str(round(spot,2))
        else:
            tit, flt = 'GAMMA-LEVELS WIN (PADRAO WIN)', '(str.contains(str.upper(syminfo.ticker), ' + q + 'WIN' + q + ') or str.contains(str.upper(syminfo.ticker), ' + q + 'IND' + q + '))'
            sc_str, cfn = 'overlay=true', f'conv(v) => math.round((v * ({round(win_spot,0)} / {round(spot,2)})) / 5) * 5'
            dy_def, h_ab, m_ab, fstr, p_ref = str(dy_pts), '9', '0', '#', 'close'
        return '\n'.join([
            '//@version=6',
            f'indicator(' + q + f'{tit}' + q + f', {sc_str}, max_bars_back=1000, max_labels_count=500, max_lines_count=500, max_boxes_count=1000)',
            'var line[] ls = array.new_line()', 'var label[] lbs = array.new_label()', 'var box[] bxs = array.new_box()',
            f'plot({p_ref}, display=display.none)',
            'show_txt = input.bool(true, ' + q + 'Mostrar Numeros nas Regioes' + q + ')',
            'gv_esc = input.float(50.0, ' + q + 'Escala G/V' + q + ')',
            'gv_off = input.int(25, ' + q + 'Offset G/V' + q + ')',
            f'gv_dy = input.float({dy_def}, ' + q + 'Altura G/V' + q + ')',
            'gv_op = input.int(35, ' + q + 'Opacidade G/V' + q + ')',
            'dex_esc = input.float(50.0, ' + q + 'Escala DEX' + q + ')',
            'dex_off = input.int(95, ' + q + 'Offset DEX' + q + ')',
            f'dex_dy = input.float({dy_def}, ' + q + 'Altura DEX' + q + ')',
            'oi_op = input.int(55, ' + q + 'Opacidade OI' + q + ')',
            cfn,
            'fmt_v(val) =>',
            '    av = math.abs(val)',
            '    sg = val < 0 ? ' + q + '-' + q + ' : ' + q + '' + q + '',
            '    av >= 1e6 ? sg + str.tostring(av/1e6, ' + q + '#.##' + q + ') + ' + q + 'M' + q + ' : av >= 1e3 ? sg + str.tostring(av/1e3, ' + q + '#.#' + q + ') + ' + q + 'k' + q + ' : sg + str.tostring(av, ' + q + '#' + q + ')',
            'add_l(t, vu, c, s) =>',
            '    v = conv(vu)',
            f'    t0 = timestamp(' + q + 'America/Sao_Paulo' + q + ', year(time,' + q + 'America/Sao_Paulo' + q + '), month(time,' + q + 'America/Sao_Paulo' + q + '), dayofmonth(time,' + q + 'America/Sao_Paulo' + q + f'), {h_ab}, {m_ab})',
            '    t1 = time >= t0 ? t0 : t0 - 86400000',
            '    array.push(ls, line.new(t1, v, time, v, color=c, width=2, style=s, xloc=xloc.bar_time))',
            f'    array.push(lbs, label.new(time, v, t + ' + q + ' (' + q + ' + str.tostring(v, ' + q + f'{fstr}' + q + ') + ' + q + ')' + q + ', style=label.style_label_left, color=color.new(c,100), textcolor=c, size=size.small, xloc=xloc.bar_time))',
            f'ks={fmt_a(ks)}', f'gcv={fmt_a(gcv)}', f'gpv={fmt_a(gpv)}', f'gcoi={fmt_a(gcoi)}', f'gpoi={fmt_a(gpoi)}', f'vc={fmt_a(vc)}', f'vp={fmt_a(vp)}', f'dcoi={fmt_a(dcoi)}', f'dpoi={fmt_a(dpoi)}', f'dnv={fmt_a(dnv)}',
            f'if barstate.islast and {flt}',
            '    for x in ls\n        line.delete(x)\n    array.clear(ls)',
            '    for x in lbs\n        label.delete(x)\n    array.clear(lbs)',
            '    for x in bxs\n        box.delete(x)\n    array.clear(bxs)',
            f'    add_l(' + q + f'Call Wall - OI {int(cw.oi/1000)}k' + q + f', {float(cw.strike)}, color.rgb(176,39,46), line.style_solid)',
            f'    add_l(' + q + f'Vanna+ - OI {int(vn.oi/1000)}k' + q + f', {float(vn.strike)}, color.rgb(0,230,118), line.style_dashed)',
            f'    add_l(' + q + 'DELTA FLIP' + q + f', {dfp}, color.rgb(153,50,204), line.style_solid)',
            f'    add_l(' + q + 'GAMMA FLIP' + q + f', {gf}, color.rgb(153,50,204), line.style_solid)',
            f'    add_l(' + q + 'SPOT' + q + f', {round(spot,2)}, color.gray, line.style_solid)',
            f'    add_l(' + q + f'Put Wall - OI {int(pw.oi/1000)}k' + q + f', {float(pw.strike)}, color.rgb(57,142,232), line.style_solid)',
            '    xb1 = bar_index + gv_off\n    xb2 = bar_index + dex_off\n    mgv=1.0\n    mgoi=1.0\n    mvol=1.0\n    mdv=1.0\n    mdoi=1.0',
            '    for i=0 to array.size(ks)-1\n        mgv:=math.max(mgv,math.abs(array.get(gcv,i)+array.get(gpv,i)))\n        mgoi:=math.max(mgoi,math.abs(array.get(gcoi,i)+array.get(gpoi,i)))\n        mvol:=math.max(mvol,math.max(array.get(vc,i),array.get(vp,i)))\n        mdv:=math.max(mdv,math.abs(array.get(dnv,i)))\n        mdoi:=math.max(mdoi,math.abs(array.get(dcoi,i)+array.get(dpoi,i)))',
            '    for i=0 to array.size(ks)-1\n        k=conv(array.get(ks,i))\n        noi=array.get(gcoi,i)+array.get(gpoi,i)\n        woi=math.max(8, math.round(math.abs(noi)/mgoi*gv_esc))\n        if math.abs(noi)>0\n            c_oi = noi>=0?color.rgb(131,20,196):color.rgb(234,12,12)\n            array.push(bxs,box.new(xb1-woi,k,xb1,k-gv_dy,border_color=c_oi,bgcolor=color.new(c_oi,oi_op),text=show_txt?fmt_v(noi):' + q + '' + q + ',text_color=color.white,text_size=size.tiny))\n        nv=array.get(gcv,i)+array.get(gpv,i)\n        wg=math.max(6, math.round(math.abs(nv)/mgv*gv_esc))\n        if math.abs(nv)>0\n            c_nv = nv>=0?color.rgb(131,20,196):color.rgb(234,12,12)\n            array.push(bxs,box.new(xb1-wg,k+gv_dy,xb1,k,border_color=c_nv,bgcolor=color.new(c_nv,gv_op),text=show_txt?fmt_v(nv):' + q + '' + q + ',text_color=color.yellow,text_size=size.tiny))\n        v_c=array.get(vc,i)\n        v_p=array.get(vp,i)\n        w1=math.max(6, math.round(v_c/mvol*gv_esc*0.8))\n        w2=math.max(6, math.round(v_p/mvol*gv_esc*0.8))\n        if v_c>0\n            array.push(bxs,box.new(xb1,k+gv_dy,xb1+w1,k,border_color=na,bgcolor=color.new(color.red,gv_op),text=show_txt?fmt_v(v_c):' + q + '' + q + ',text_color=color.rgb(255,150,150),text_size=size.tiny))\n        if v_p>0\n            array.push(bxs,box.new(xb1,k,xb1+w2,k-gv_dy,border_color=na,bgcolor=color.new(color.green,gv_op),text=show_txt?fmt_v(v_p):' + q + '' + q + ',text_color=color.rgb(150,255,170),text_size=size.tiny))\n        doi=array.get(dcoi,i)+array.get(dpoi,i)\n        wdoi=math.max(8, math.round(math.abs(doi)/mdoi*dex_esc))\n        if math.abs(doi)>0\n            c_doi = doi>=0?color.rgb(20,160,60):color.rgb(234,12,12)\n            array.push(bxs,box.new(doi>=0?xb2:xb2-wdoi,k,doi>=0?xb2+wdoi:xb2,k-dex_dy,border_color=c_doi,bgcolor=color.new(c_doi,oi_op),text=show_txt?fmt_v(doi):' + q + '' + q + ',text_color=color.white,text_size=size.tiny))\n        dn=array.get(dnv,i)\n        wdn=math.max(6, math.round(math.abs(dn)/mdv*dex_esc))\n        if math.abs(dn)>0\n            c_dn = dn>=0?color.rgb(20,160,60):color.rgb(234,12,12)\n            array.push(bxs,box.new(dn>=0?xb2:xb2-wdn,k+dex_dy,dn>=0?xb2+wdn:xb2,k,border_color=c_dn,bgcolor=color.new(c_dn,gv_op),text=show_txt?fmt_v(dn):' + q + '' + q + ',text_color=color.yellow,text_size=size.tiny))'
        ])

    if 'gen_sel' not in st.session_state:
        st.session_state['gen_sel'] = None
    c_a, c_b = st.columns(2)
    if c_a.button('🇺🇸 Gerar Indicador EWZ (TradingView)', key='btn_ewz_v2', width='stretch'):
        st.session_state['gen_sel'] = 'EWZ'
    if c_b.button('🇧🇷 Gerar Indicador BRA50 (TradingView)', key='btn_bra_v2', width='stretch'):
        st.session_state['gen_sel'] = 'BRA50'
    c_c, c_d = st.columns(2)
    if c_c.button('📈 Gerar Indicador WIN (TradingView)', key='btn_win_v2', width='stretch'):
        st.session_state['gen_sel'] = 'WIN'
    if c_d.button('💻 Gerar Indicador Profit (NTSL)', key='btn_prof_v2', width='stretch'):
        st.session_state['gen_sel'] = 'PROFIT'
    sel = st.session_state['gen_sel']
    if sel in ['EWZ', 'BRA50', 'WIN']:
        cod = build_pine(sel)
        st.code(cod, language='pinescript')
        st.download_button(f'💾 Baixar gamma_{sel.lower()}.pine', cod, f'gamma_{sel.lower()}.pine')
    elif sel == 'PROFIT':
        from profit_ntsl import gerar_codigo_profit
        c_prof = gerar_codigo_profit(spot, win_spot, df_sub, cw, pw, vn, dfp, gf)
        st.success('Indicador Profit NTSL (HorizontalLineCustom) gerado com sucesso! Cole no Editor de Estrategias:')
        st.code(c_prof, language='pascal')
        st.download_button('💾 Baixar Profit (.ntsl)', c_prof, 'gamma_win_profit.ntsl')
