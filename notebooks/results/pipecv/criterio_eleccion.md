# Criterio de elección del modelo

1. Para cada modelo se toma la mejor estrategia del ajuste fino según el AUC de validación cruzada
   (GroupKFold(5) por empresa, con todo el preprocesamiento dentro del pipeline).
2. Cada modelo se reentrena con esa estrategia y sus hiperparámetros sobre todo el conjunto de
   entrenamiento (modelo final).
3. Se elige el modelo final con mayor AUC de entrenamiento (celda `pipecv_final`). El test no
   interviene en la elección; sus métricas se informan.

Resultado (05/11/2026, con la cobertura de intereses = Resultado Operativo / Intereses Perdidos):
el Random Forest (IQR + Yeo-Johnson + RFECV, 107 variables, sin balanceo) tiene el mayor AUC de
entrenamiento (0,8252), seguido por XGBoost (0,8074), el MLP (0,7423), el árbol de decisión (0,7256)
y la regresión logística (0,7110). En validación cruzada, los cuatro primeros quedan dentro de la
variación entre particiones: regresión logística 0,6922, MLP 0,6905, Random Forest 0,6881 y
XGBoost 0,6827 (desvíos de 0,034 a 0,045); el árbol, 0,6608.

Límite a declarar: el AUC de entrenamiento se calcula sobre los mismos datos con que se ajustó el
modelo y favorece a los más flexibles. El Random Forest tiene la mayor brecha entre entrenamiento y
validación cruzada (0,825 frente a 0,688). En test obtiene 0,7510 (IC 0,694 a 0,802).

Antecedente: el 04/11 se elegía por el mayor AUC de validación cruzada (regresión logística, con la
cobertura anterior); el 03/11, por el AUC y el recall de entrenamiento (Random Forest).
