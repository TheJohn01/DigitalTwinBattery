import numpy as np
import pandas as pd
import numpy_financial as npf

def calcular_tea(
    capex_eur_kwh=130.0,
    capacidade_kwh=100.0,
    custo_eletricidade_eur_kwh=0.20,
    receita_arbitragem_eur_kwh=0.35,
    degradacao_anual_pct=2.0,
    taxa_desconto_wacc=0.07,
    anos_operacao=15,
    ciclos_por_dia=1.0  # Pressuposto tornado explícito
):
    capex_inicial = capex_eur_kwh * capacidade_kwh
    opex_anual_fixo = capex_inicial * 0.015
    
    anos = np.arange(0, anos_operacao + 1)
    fluxo_caixa = np.zeros(anos_operacao + 1)
    fluxo_caixa[0] = -capex_inicial
    
    energia_descarregada_anual = []
    
    for t in range(1, anos_operacao + 1):
        cap_disponivel = capacidade_kwh * ((1 - (degradacao_anual_pct / 100.0)) ** (t - 1))
        energia_ano = cap_disponivel * 0.80 * (365 * ciclos_por_dia)
        energia_descarregada_anual.append(energia_ano)
        
        custo_carregamento = energia_ano * custo_eletricidade_eur_kwh
        receita_venda = energia_ano * receita_arbitragem_eur_kwh
        fluxo_caixa[t] = receita_venda - custo_carregamento - opex_anual_fixo

    # Cálculo de NPV, IRR e Payback
    fatores_desconto = (1 + taxa_desconto_wacc) ** anos
    npv = np.sum(fluxo_caixa / fatores_desconto)

    # IRR é instável quando o fluxo de caixa não tem mudança de sinal
    # (ex.: todos os períodos negativos ou todos positivos). Protegido.
    try:
        irr_val = npf.irr(fluxo_caixa)
        if irr_val is None or not np.isfinite(irr_val):
            irr = np.nan
        else:
            irr = float(irr_val) * 100.0  # Retorno em %
    except Exception:
        irr = np.nan

    fc_descontado = fluxo_caixa / fatores_desconto
    cum_fc = np.cumsum(fc_descontado)
    payback_anos = np.argmax(cum_fc >= 0) if np.any(cum_fc >= 0) else np.nan

    # Converter a lista em array NumPy para cálculos vetorizados
    energia_array = np.array(energia_descarregada_anual, dtype=float)
    denominador_desconto = fatores_desconto[1:]

    # O fatiamento [1:] garante que os 15 anos de energia cruzam com os anos 1 a 15 de desconto
    custos_descontados = capex_inicial + np.sum(
        (opex_anual_fixo + (energia_array * custo_eletricidade_eur_kwh)) / denominador_desconto
    )

    # LCOS - Levelized Cost of Storage
    # Protege a divisão: se não houver energia entregue (ou for NaN/inf),
    # o LCOS é indefinido em vez de produzir inf/erro numérico.
    energia_descontada_total = np.sum(energia_array / denominador_desconto)
    if not np.isfinite(energia_descontada_total) or energia_descontada_total <= 0:
        lcos_eur_kwh = np.nan
    else:
        lcos_eur_kwh = custos_descontados / energia_descontada_total

    return pd.DataFrame([{
        "CAPEX Inicial (€)": round(capex_inicial, 2),
        "NPV (€)": round(npv, 2),
        "IRR (%)": round(irr, 2) if np.isfinite(irr) else "N/A",
        "Payback Descontado (Anos)": int(payback_anos) if np.isfinite(payback_anos) else "N/A",
        "LCOS (€/kWh)": round(lcos_eur_kwh, 4) if np.isfinite(lcos_eur_kwh) else "N/A"
    }])
