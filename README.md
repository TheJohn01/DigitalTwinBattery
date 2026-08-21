# DigitalTwinBattery
# Digital Twin para Simulação, Degradação e Avaliação Multicritério de Baterias

## Visão geral

Este projeto desenvolve um **Digital Twin computacional de baterias recarregáveis**, combinando simulação eletroquímica, envelhecimento, análise técnico-económica e avaliação ambiental num único ambiente interativo.

O objetivo é criar uma ferramenta de engenharia capaz de comparar diferentes tecnologias de armazenamento de energia e analisar, de forma integrada:

- comportamento eletroquímico;
- degradação ao longo dos ciclos;
- Estado de Saúde (SOH);
- retenção de capacidade;
- comportamento térmico;
- crescimento da camada SEI;
- perda de lítio útil;
- custo do sistema;
- indicadores de viabilidade económica;
- pegada de carbono;
- diferenças entre utilização veicular e estacionária.

O projeto compara quatro químicas:

| Tecnologia | Abreviatura |
|---|---|
| Níquel-Manganês-Cobalto | NMC |
| Lítio-Ferro-Fosfato | LFP |
| Níquel-Cobalto-Alumínio | NCA |
| Chumbo-Ácido | Lead-Acid |

A aplicação disponibiliza estes modelos através de uma interface web desenvolvida em **Streamlit**, permitindo alterar parâmetros de operação e visualizar os resultados da simulação.

---

## Objetivos

O projeto foi desenvolvido com os seguintes objetivos principais:

1. Implementar simulações eletroquímicas utilizando **PyBaMM**.
2. Estudar o impacto de diferentes taxas de carga rápida.
3. Avaliar a degradação das baterias ao longo de múltiplos ciclos.
4. Extrair indicadores de desempenho como SOH e retenção de capacidade.
5. Comparar diferentes químicas de bateria sob condições equivalentes.
6. Integrar os resultados num **Digital Twin interativo**.
7. Implementar uma análise técnico-económica (TEA).
8. Implementar uma avaliação do ciclo de vida simplificada (LCA).
9. Automatizar testes dos módulos matemáticos através de `pytest`.
10. Estruturar o projeto como um portfólio técnico de Engenharia Química orientado para **transição energética, armazenamento de energia, ciência de dados e Indústria 4.0**.

---

# Simulação eletroquímica

A componente eletroquímica utiliza o **PyBaMM (Python Battery Mathematical Modelling)** para executar simulações baseadas no modelo **Doyle-Fuller-Newman (DFN)**.

Foram implementados protocolos de carga rápida entre:

**1C → 4C**

e estudado o comportamento da bateria ao longo de múltiplos ciclos.

A simulação permite analisar, entre outros:

- tensão;
- corrente;
- temperatura;
- capacidade;
- degradação;
- crescimento da camada SEI;
- perda de lítio útil;
- SOH;
- retenção de capacidade.

Os resultados podem ser exportados para análise posterior.
