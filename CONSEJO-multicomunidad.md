# Veredicto del consejo · cómo llevar la aplicación a las 17 comunidades

Cinco asesores en paralelo, revisión anónima entre ellos y síntesis final.
9 de septiembre de 2026.

---

## En lo que coinciden los cinco

- **Los mapas de campos salen del código a ficheros de datos.** Unanimidad. La
  discusión fue solo sobre cuándo, no sobre si.
- **El coste real no es escribir el mapeo, es saber que el mapeo está bien.**
- **LibreOffice tiene que desaparecer del ordenador del cliente.** Es 300 MB de
  programa para calcular dos fórmulas, y es la primera fuente de llamadas de
  soporte.
- **Nadie compra «17 comunidades».** Cada instalador trabaja en una, como mucho
  dos. Lo que se vende es *su* comunidad y la confianza en que el papel sale bien.
- **Nunca generar y dar por bueno.** Revisión previa antes del documento
  definitivo.

## En lo que chocan

**¿Modelo de datos común ahora o después?** Dos asesores dicen que el modelo
común *es* el producto, porque el REBT es estatal y lo que hay debajo es idéntico
en Cádiz y en Lugo. Otro dice que con una sola comunidad delante es adivinar.

Se resuelve separando el **núcleo del REBT**, que ya existe implícito en el
formulario actual, de la taxonomía completa del expediente, que sí sería
adivinar.

**¿Construir primero o vender primero?** Dos asesores dicen congelar el código y
conseguir tres instaladores de otras comunidades que paguen por adelantado, y que
ellos decidan cuál es la segunda comunidad.

**Actualizaciones automáticas de impresos.** Propuesta rechazada. Cambiar sin
avisar el contenido de un documento que firma un habilitado ante la
administración es justo lo que no debe pasar. Actualizaciones **voluntarias**,
con registro de cambios, y versión congelada por expediente.

## Lo que nadie había visto

- **Puede que no haya 17 impresos distintos, sino 5 o 6 familias.** El CIE tiene
  modelo estatal y varias comunidades lo reutilizan casi igual. Hacer el censo
  real antes de arquitectar nada puede reducir el problema a un tercio.
- **El trabajo de verdad es el segundo expediente, no el primero.** Reutilizar
  datos del cliente y del cuadro tipo, y sobre todo el bucle de **subsanación**:
  cuando Industria devuelve el expediente pidiendo corregir un campo, hay que
  cambiar ese campo y rehacer los seis documentos sin repetir todo.
- **El coste recurrente no es mapear, es enterarse de que el impreso cambió.**
  Guardar el impreso original dentro del paquete y generar siempre contra esa
  copia congelada.
- **RGPD**: al vender la aplicación pasas a ser encargado del tratamiento de los
  datos de los clientes de otros instaladores.
- **Derechos de redistribución** de los impresos oficiales de 17
  administraciones, antes de meterlos en un ZIP que se vende.
- **Vender el servicio en vez del programa**: tramitar el expediente por 60-90 €
  el punto. Mismo trabajo hecho, cero soporte telefónico, y valida la demanda
  esta semana.

---

## La recomendación

### Paquetes de comunidad declarativos, con motores en el código

Ni plugins (código ajeno junto a documentos firmados) ni un adaptador en Python
por comunidad. **Ficheros de datos + tres motores genéricos.**

```
nucleo/
  modelo.py          expediente canónico + validaciones
  calculos.py        intensidad, caída, potencia admisible
  motores/
    acroform.py      PDF de formulario (lo que ya existe)
    overlay.py       PDF plantilla + texto por coordenadas
    copiar.py        portales web: pantalla de copiar y pegar
packs/
  madrid/2026.1/
    manifiesto.json  comunidad, versión, vigencia, huellas
    documentos/      un JSON por impreso
    plantillas/      los originales CONGELADOS dentro del paquete
    golden/          expediente de prueba y salida esperada
herramientas/
  mapeador/          web local: clic en la caja, eliges el campo
```

El conocimiento que ya se ha pagado caro (el mapeo por coordenada del anexo IVE,
las casillas con estado `Sí`) vive en el motor, no en el paquete.

### El mapeador es el producto

Convierte «programar una comunidad» en «una tarde de desplegables». Se construye
reutilizando el código con el que ya se dibujaron las cajas sobre el PDF. Es lo
que permite que un cliente de otra comunidad aporte su propio mapeo y tú solo lo
certifiques.

### Cómo comprobar un impreso nuevo sin revisarlo a ojo

Un expediente de prueba con un valor único e irrepetible por campo (`TIT_01`,
`CUPS_07`…). Se rellenan los impresos, se extrae el texto y se guarda en qué
página y en qué coordenada cayó cada valor. Se revisa a ojo **una vez**. A partir
de ahí, el ordenador avisa si algo se ha movido.

### Quitar LibreOffice

Las fórmulas del CIE son deterministas y ya se ha reimplementado una (la del
CUPS). Se reimplementan las otras dos, la hoja vacía se exporta a PDF **una sola
vez, en tu ordenador**, y ese PDF pasa a ser la plantilla de coordenadas. El
cliente instala Python y nada más.

Antes de hacerlo hay que confirmar que la administración acepta el PDF y no exige
el `.xls` original.

### Lanzar con Madrid y dos más

Las dos segundas no las elige el catálogo de PDFs que ya tienes: las elige el
primer instalador que pague por adelantado en esa comunidad. Él aporta los
impresos, conoce el procedimiento, y su expediente admitido es el único test que
existe de verdad.

El mensaje no es «CIE, MTD, anexo IVE, BT-1134F1». Es «el papeleo de un punto de
recarga, de dos horas a diez minutos», con el número de expedientes ya aprobados
en Industria de Madrid delante.

### Cinco salvaguardas, porque esto lo firma un habilitado

1. **BORRADOR por defecto**, con marca de agua, hasta que confirmas la revisión.
2. **Campos sin mapear en rojo** y generación bloqueada si falta uno obligatorio.
3. **Diferencia contra el último expediente aceptado** de esa comunidad.
4. **Trazabilidad**: cada PDF archivado junto a la versión del paquete, la huella
   del impreso original y los datos de entrada. Reproducible años después.
5. **Condiciones de uso** que dejen claro que la autoría técnica y la
   responsabilidad son del instalador que firma, y que la aplicación es utillaje.

---

## Lo primero que hay que hacer

**La red de seguridad de Madrid, antes de tocar nada más.** Un expediente de
prueba con un valor único por campo, generar los seis documentos, guardar dónde
cayó cada valor y revisarlo a ojo una vez.

Es un día de trabajo. Protege lo único que hoy funciona, es requisito para tocar
la arquitectura sin romper Madrid, y no se desperdicia decidas lo que decidas
después.

---

## Las cinco posturas, en una línea

| Asesor | Postura |
|---|---|
| El Contrario | El fallo no es la arquitectura, es que no tienes validación fuera de Madrid. Congela y consigue clientes que presenten de verdad. |
| Primeros Principios | La unidad de expansión no es la comunidad, es el primer cliente que paga en ella. El REBT es lo único que vendes. |
| El Expansionista | El activo es el esquema común. Amplía a cualquier instalación eléctrica y a licencias con fabricantes. |
| El Forastero | Nadie compra «17 comunidades». LibreOffice mata más ventas que cualquier decisión técnica. |
| El Ejecutor | Seis semanas: ficheros de datos, red de regresión, mapeador, dos comunidades. |

Cuatro de los cinco revisores señalaron al Ejecutor como la respuesta más fuerte,
por ser la única ejecutable y la única con red de seguridad. El revisor de riesgo
legal se descolgó a favor del Contrario, por la cadena de responsabilidad.
