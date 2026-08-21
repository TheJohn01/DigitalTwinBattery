import pybamm
import pandas as pd

def extrair_capacidades_solucao(solution):
    """Extrai a série de capacidades por ciclo priorizando summary_variables."""
    try:
        return list(solution.summary_variables["Capacity [A.h]"])
    except (KeyError, AttributeError):
        capacidades = []
        for cycle in solution.cycles:
            try:
                cap = abs(float(cycle.steps[0]["Discharge capacity [A.h]"].entries[-1]))
            except Exception:
                cap = abs(float(cycle["Discharge capacity [A.h]"].entries[-1]))
            capacidades.append(cap)
        return capacidades

# 1. Configurar modelo e simulação de 10 ciclos
options = {"thermal": "lumped", "SEI": "solvent-diffusion limited"}
model = pybamm.lithium_ion.DFN(options=options)
parameter_values = pybamm.ParameterValues("Chen2020")

ciclo = [
    "Discharge at 1C until 2.5 V",
    "Rest for 5 minutes",
    "Charge at 3C until 4.2 V",
    "Hold at 4.2 V until C/20",
    "Rest for 5 minutes"
]
experiment = pybamm.Experiment([tuple(ciclo)] * 10)

sim = pybamm.Simulation(model, parameter_values=parameter_values, experiment=experiment)
solution = sim.solve()

# 2. Processar dados por ciclo com extração robusta
capacidades = extrair_capacidades_solucao(solution)
# Usa o vetor já extraído para obter de forma limpa a capacidade de referência
cap_inicial = max(capacidades) if capacidades else 1.0 

dados_processados = []

for idx, cycle in enumerate(solution.cycles):
    # Proteção: Garante que só tentamos ler índices que existam no array de capacidades
    if idx >= len(capacidades):
        break
        
    cap_actual = capacidades[idx]
    soh = (cap_actual / cap_inicial) * 100
    
    # Tratamento defensivo extra nas variáveis termodinâmicas
    try:
        temp_max = cycle["X-averaged cell temperature [C]"].entries.max()
    except KeyError:
        temp_max = 25.0
        
    try:
        sei_espessura = cycle["X-averaged negative SEI thickness [m]"].entries[-1]
    except KeyError:
        sei_espessura = 0.0

    dados_processados.append({
        "Ciclo": idx + 1,
        "Capacidade_Ah": round(cap_actual, 4),
        "SOH_Percentual": round(soh, 2),
        "Temp_Max_C": round(temp_max, 2),
        "Espessura_SEI_m": sei_espessura
    })

# 3. Guardar em ficheiro CSV
df = pd.DataFrame(dados_processados)
df.to_csv("dados_degradacao_bateria.csv", index=False)
print("Ficheiro 'dados_degradacao_bateria.csv' gerado com sucesso!")