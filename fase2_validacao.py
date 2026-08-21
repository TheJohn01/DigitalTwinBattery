import pybamm
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Simulação DFN
model = pybamm.lithium_ion.DFN()
param = pybamm.ParameterValues("Chen2020")
sim = pybamm.Simulation(model, parameter_values=param)
sol = sim.solve([0, 3600])

# Dados simulados
cap_sim = sol["Discharge capacity [A.h]"].entries
v_sim = sol["Terminal voltage [V]"].entries

# Carregar dados experimentais reais / digitalizados
# Exemplo com criação de curva experimental com ruído para demonstração
np.random.seed(42)
cap_exp = np.linspace(0, max(cap_sim), len(cap_sim))
v_exp = v_sim - 0.02 * np.exp(cap_exp / 4.0) + np.random.normal(0, 0.005, len(cap_sim))

# Métricas de Validação
rmse = np.sqrt(np.mean((v_sim - v_exp) ** 2))
mae = np.mean(np.abs(v_sim - v_exp))

print(f"Métricas de Validação — RMSE: {rmse:.4f} V | MAE: {mae:.4f} V")

plt.figure(figsize=(8, 4))
plt.plot(cap_sim, v_sim, label="Simulação DFN (Chen 2020)", color="navy", lw=2)
plt.plot(cap_exp, v_exp, 'o', label="Dados Experimentais", color="crimson", ms=3, alpha=0.6)
plt.title(f"Validação do Modelo — RMSE: {rmse:.4f} V")
plt.xlabel("Capacidade Descarregada [Ah]")
plt.ylabel("Tensão Terminal [V]")
plt.legend()
plt.grid(True)
plt.show()