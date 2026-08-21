import pandas as pd

def calcular_lca_bateria(
    capacidade_kwh=60.0,
    massa_kg=380.0,
    quimica="NMC",
    vida_util_km=200000.0,
    consumo_kwh_km=0.16,  # Pressuposto configurável
    mix_eletrico_g_co2_kwh=210.0,
    aplicacao_veicular=True
):
    fatores_fabrico = {"NMC": 73.0, "LFP": 58.0, "NCA": 70.0, "Chumbo-Ácido": 35.0}
    fator_fab = fatores_fabrico.get(quimica, 70.0)

    co2_extracao = massa_kg * 11.5
    co2_fabrico = capacidade_kwh * fator_fab
    
    # Correção da inconsistência: Chumbo-Ácido ou sistemas estacionários não usam perfil EV por km
    if aplicacao_veicular and quimica != "Chumbo-Ácido":
        co2_uso = (vida_util_km * consumo_kwh_km) * (mix_eletrico_g_co2_kwh / 1000.0)
    else:
        # Perfil estacionário: baseado em 3000 ciclos completos
        co2_uso = (capacidade_kwh * 3000 * 0.85) * (mix_eletrico_g_co2_kwh / 1000.0)

    co2_reciclagem = -1 * massa_kg * 4.2
    co2_total = co2_extracao + co2_fabrico + co2_uso + co2_reciclagem
    pegada_especifica = co2_total / capacidade_kwh

    df_fases = pd.DataFrame([
        {"Fase": "1. Extração de Matérias-Primas", "Emissões (kg CO2eq)": round(co2_extracao, 2)},
        {"Fase": "2. Fabrico de Células e Pack", "Emissões (kg CO2eq)": round(co2_fabrico, 2)},
        {"Fase": "3. Fase de Operação/Uso", "Emissões (kg CO2eq)": round(co2_uso, 2)},
        {"Fase": "4. Reciclagem e Fim-de-Vida", "Emissões (kg CO2eq)": round(co2_reciclagem, 2)},
        {"Fase": "TOTAL (Cradle-to-Grave)", "Emissões (kg CO2eq)": round(co2_total, 2)}
    ])

    return df_fases, round(pegada_especifica, 2)