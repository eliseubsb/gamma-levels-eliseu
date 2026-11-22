def gerar_codigo_profit(spot, win_spot, df_sub, cw, pw, vn, dfp, gf):
    fator = win_spot / spot
    conv = lambda v: round((float(v) * fator) / 5.0) * 5.0
    niveis = []
    def add_nv(px_usd, cor, est, esp, txt):
        px_w = conv(px_usd)
        if px_w > 0 and all(abs(px_w - x[0]) >= 35 for x in niveis):
            niveis.append((px_w, cor, est, esp, txt))

    add_nv(cw.strike, 1, 0, 2, f'Call Wall (OI {int(cw.oi/1000)}k) - resistencia estrutural (MM vende rali) · EWZ ${float(cw.strike):.2f}')
    add_nv(vn.strike, 7, 1, 2, f'Vanna+ (OI {int(vn.oi/1000)}k) - fluxo comprador se IV cair · EWZ ${float(vn.strike):.2f}')
    add_nv(gf, 2, 1, 2, f'Gamma Flip - vira o regime long/short gamma · +D/Flip · EWZ ${float(gf):.2f}')
    add_nv(dfp, 3, 2, 2, f'Delta Flip - equilibrio de delta dos dealers · EWZ ${float(dfp):.2f}')
    add_nv(spot, 5, 2, 1, f'Spot - referencia de abertura · EWZ ${float(spot):.2f}')
    add_nv(pw.strike, 9, 0, 2, f'Put Wall (OI {int(pw.oi/1000)}k) - suporte estrutural (MM compra queda) · EWZ ${float(pw.strike):.2f}')

    sub_k = df_sub[(df_sub['strike'] >= spot * 0.90) & (df_sub['strike'] <= spot * 1.12)].copy()
    if not sub_k.empty:
        agg = sub_k.groupby('strike').agg(gex=('gex_oi','sum'), gvol=('gex_vol','sum'), dex=('dex_oi','sum'), van=('van_oi','sum')).reset_index()
        agg['imp'] = agg['gex'].abs() + agg['dex'].abs()*0.25 + agg['gvol'].abs()*1.5
        agg = agg.sort_values('imp', ascending=False)
        for _, r in agg.iterrows():
            if len(niveis) >= 18: break
            k = float(r['strike'])
            sk = sub_k[sub_k['strike'] == k]
            c_oi = int(sk[sk['is_c']]['openInterest'].sum() / 1000)
            p_oi = int(sk[~sk['is_c']]['openInterest'].sum() / 1000)
            lado_c = 'OTM' if k > spot else 'ITM'
            lado_p = 'ITM' if k > spot else 'OTM'
            g_m = r['gex'] / 1e6
            d_m = r['dex'] / 1e6
            if r['gex'] >= 0 and k >= spot:
                cor, est, tit = 7, 2, 'Gamma Wall - teto defendido trava alta'
            elif r['gex'] >= 0 and k < spot:
                cor, est, tit = 6, 2, 'Sup · Long Gamma - zona de absorcao (MM compra queda)'
            elif r['gex'] < 0 and k < spot:
                cor, est, tit = 0, 1, 'Gamma Risk - piso solta acelera queda'
            else:
                cor, est, tit = 2, 2, 'Res Fragil - short gamma acima do spot (acelera rompimento)'
            txt = f'{tit} · {c_oi}k Calls {lado_c} · {p_oi}k Puts {lado_p} · GEX:{g_m:+.1f}M DEX:{d_m:+.1f}M · EWZ ${k:.2f}'
            add_nv(k, cor, est, 2, txt)

    niveis.sort(key=lambda x: x[0], reverse=True)
    niveis = niveis[:20]
    while len(niveis) < 20:
        niveis.append((0.0, 1, 0, 2, ''))
    px_l = [f'  px{i+1:02d}({niveis[i][0]:.1f});' for i in range(20)]
    c_l  = [f'  c{i+1:02d}({niveis[i][1]});' for i in range(20)]
    s_l  = [f'  s{i+1:02d}({niveis[i][2]});' for i in range(20)]
    w_l  = [f'  w{i+1:02d}({niveis[i][3]});' for i in range(20)]
    t_l  = [f'  t{i+1:02d}("{niveis[i][4]}");' for i in range(20)]
    calls = [f'    if (px{i+1:02d} > 0) then HorizontalLineCustom(px{i+1:02d}, CorDe(c{i+1:02d}), w{i+1:02d}, s{i+1:02d}, t{i+1:02d}, 10, tpTopRight, 0, 0, 0, 900, 1900);' for i in range(20)]
    hdr = [
        '//====================== NIVEIS (STRIKE) + COR + ESTILO + ESPESSURA + LEGENDAS ======================',
        '// COR:    0=Maroon 1=Red 2=Yellow 3=Fuchsia 4=White 5=Gray 6=Aqua',
        '//         7=Lime 8=Green 9=Blue 10=Purple 11=Black 12=Teal 13=Navy 14=Olive',
        '// ESTILO: 0=Solida 1=Tracejada 2=Pontilhada 3=TracoPonto 4=TracoPontoPonto',
        f'// Gerado automaticamente pelo Painel WebEWZ - WIN {int(win_spot)} | EWZ ${spot:.2f}',
        '//========================================================================',
        '', 'input'
    ]
    body = [
        '', 'var', '  linesDrawn : boolean;', '',
        '//------- traduz codigo de cor para constante clXxx -------',
        'function CorDe(cd: integer): integer;', 'begin',
        '  if (cd = 0) then CorDe := clMaroon',
        '  else if (cd = 1) then CorDe := clRed',
        '  else if (cd = 2) then CorDe := clYellow',
        '  else if (cd = 3) then CorDe := clFuchsia',
        '  else if (cd = 4) then CorDe := clWhite',
        '  else if (cd = 5) then CorDe := clGray',
        '  else if (cd = 6) then CorDe := clAqua',
        '  else if (cd = 7) then CorDe := clLime',
        '  else if (cd = 8) then CorDe := clGreen',
        '  else if (cd = 9) then CorDe := clBlue',
        '  else if (cd = 10) then CorDe := clPurple',
        '  else if (cd = 11) then CorDe := clBlack',
        '  else if (cd = 12) then CorDe := clTeal',
        '  else if (cd = 13) then CorDe := clNavy',
        '  else if (cd = 14) then CorDe := clOlive',
        '  else CorDe := clRed;', 'end;', '',
        'begin',
        '  if ((not linesDrawn) and',
        '     ((GetAsset() = "WINFUT") or (GetAsset() = "INDFUT") or',
        '      (GetAsset() = "WINZ26") or (GetAsset() = "INDZ26") or',
        '      (GetAsset() = "WING27") or (GetAsset() = "INDG27") or',
        '      (GetAsset() = "WINJ27") or (GetAsset() = "INDJ27"))) then',
        '  begin'
    ] + calls + ['    linesDrawn := true;', '  end;', 'end;']
    return '\n'.join(hdr + px_l + [''] + c_l + [''] + s_l + [''] + w_l + [''] + t_l + body)
