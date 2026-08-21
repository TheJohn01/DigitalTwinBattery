import pybamm
import matplotlib.pyplot as plt

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

crates_carga = [1.0, 2.0, 3.0, 4.0]
resultados = {}

for c_rate in crates_carga:
    options = {"thermal": "lumped", "SEI": "solvent-diffusion limited"}
    model = pybamm.lithium_ion.DFN(options=options)
    param = pybamm.ParameterValues("Chen2020")
    
    # Limites temporais explícitos ("for 2 hours") para estabilizar a convergência do IDAKLU
    ciclo = [
        "Discharge at 1C for 2 hours or until 2.5 V",
        "Rest for 5 minutes",
        f"Charge at {c_rate}C for 2 hours or until 4.2 V",
        "Hold at 4.2 V until C/20",
        "Rest for 5 minutes"
    ]
    
    exp = pybamm.Experiment([tuple(ciclo)] * 20)
    sim = pybamm.Simulation(model, parameter_values=param, experiment=exp)
    
    print(f"A simular ciclo de carga a {c_rate}C...")
    try:
        sol = sim.solve()
        caps = extrair_capacidades_solucao(sol)
        resultados[f"{c_rate}C"] = caps
        print(f"Sucesso a {c_rate}C!")
    except Exception as e:
        print(f"Aviso: Simulação não convergiu a {c_rate}C ({e})")

# Renderização do Gráfico
plt.figure(figsize=(9, 5))
for label, caps in resultados.items():
    plt.plot(range(1, len(caps) + 1), caps, marker='o', label=f"Carga Rápida {label}")

plt.xlabel("Número de Ciclos")
plt.ylabel("Capacidade Descarregada [Ah]")
plt.title("Impacto de Múltiplas Taxas de Carga Rápida no Envelhecimento (DFN)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
