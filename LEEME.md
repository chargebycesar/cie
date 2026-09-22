# Boletines IRVE · Comunidad de Madrid

> **Esta es la versión de escritorio, en Python.** La que se usa ahora es la de
> navegador, que está en `docs/` y se publica en GitHub Pages. Mira el
> [README.md](README.md). Esta se conserva porque comparte los impresos y porque
> `herramientas/` la necesita para preparar el CIE cuando cambie el modelo.

Aplicación de escritorio para generar el expediente completo de un punto de
recarga de vehículo eléctrico rellenando **un solo formulario**.

Todo ocurre en tu ordenador. No hay nube, no hay cuentas y los datos de los
clientes no salen de la carpeta `salida\`.

---

## Cómo se arranca

Doble clic en **`iniciar.bat`**.

Se abre una ventana negra (el servidor) y el navegador con la aplicación. Para
cerrarla, cierra la ventana negra.

### Qué necesita el ordenador

Solo **Python 3.10 o superior**. Si no lo tienes, `iniciar.bat` te avisa y te da
el enlace. Al instalarlo, marca la casilla **«Add python.exe to PATH»**.

La librería que lee los PDF (`pymupdf`) la instala `iniciar.bat` sola la primera
vez. **Ya no hace falta LibreOffice.**

---

## Qué genera

Cada expediente crea una carpeta en `salida\APELLIDOS_NOMBRE_fecha\` con:

| Documento | Origen |
|---|---|
| `CIE.pdf` y `CIE.xls` | Certificado de Instalación Eléctrica |
| `MTD - Memoria Tecnica de Diseno.pdf` | Memoria técnica, 6 páginas |
| `Anexo IVE - declaracion ITC-BT-52.pdf` | Declaración de montaje de IVE |
| `Solicitud de inscripcion BT-1134F1.pdf` | Solicitud de inscripción |
| `Autorizacion del titular al instalador.pdf` | Autorización de gestión |
| `Anexo - inspeccion periodica del garaje.pdf` | Solo si marcas la casilla |
| `datos.json` | Los datos que metiste, para rehacerlo |

Los PDF salen **editables**: si algo hay que retocar, se abre y se corrige sin
volver a empezar.

---

## Cómo se usa

1. **Titular**: NIF, nombre, apellidos y dirección.
2. **Emplazamiento**: si el punto está en la misma dirección, deja la casilla
   marcada y no escribes nada. Añade plaza y planta.
3. **Instalación**: elige **6 mm²** o **10 mm²**, el esquema, la potencia y los
   **metros de línea**. Escribe el CUPS y la distribuidora se rellena sola.
4. Pulsa **Generar documentos**.

El formulario se guarda solo mientras escribes. Si cierras el navegador por
error, al volver está todo como lo dejaste.

En la pestaña **Expedientes** puedes reabrir cualquiera y rehacerlo.

La pantalla va en cuatro apartados y con los valores de partida ya puestos:

1. **Cliente y emplazamiento**: datos del titular, plaza y planta. Si el punto
   está en la misma dirección, no escribes nada más.
2. **La obra**: longitud, potencia, CUPS y el origen de la línea.
3. **Conductor y protecciones**: todo desplegables. Al elegir la **sección** se
   ajustan solas la protección, el magnetotérmico y el diferencial, pero puedes
   cambiar cualquiera: poner un diferencial de 63 A con un magnetotérmico de
   32 A, o un tubo de 25 o de 40 en vez del habitual de 32.
4. **Comunidad de propietarios**: opcional.

En la práctica solo tienes que escribir NIF, nombre, apellidos, dirección,
localidad, plaza, planta, CUPS y metros de línea. Lo demás viene puesto.

### Lo que calcula solo

- **Intensidad de cálculo** a partir de potencia, tensión y tipo de suministro.
- **Potencia máxima admisible**, que sale de las protecciones y no del cargador:
  32 A a 230 V son 7,36 kW y 40 A son 9,2 kW. Es lo que va en el CIE y en las
  columnas «Potencia Máxima Admisible» del MTD y del anexo.
- **Caída de tensión** en voltios y en porcentaje, con la fórmula del REBT y
  conductividad 48 para el cobre, el mismo valor de tu hoja
  `CAIDA DE TENSION.xlsx`. Es la que se escribe en las columnas «Caída de
  Tensión Máxima (V)» de los impresos. En pantalla verás además el límite del
  5 % que fija la ITC-BT-52, y avisa si te pasas.
- **Comprobación de la letra del NIF** del titular, sea DNI, NIE o CIF.
- **El código postal**, que la aplicación recuerda de cada localidad que
  escribes. La primera vez lo pones tú; a partir de ahí lo pone sola. No inventa
  ninguno: solo recuerda los tuyos, y los ves en Configuración.

Los campos que salen ya escritos llevan **fondo blanco**, para que se distingan
de un vistazo de los huecos que quedan por rellenar, que conservan el sombreado
del impreso.
- **Empresa distribuidora** a partir de los cuatro dígitos del CUPS.
- **Comprobación del CUPS**: valida las dos letras de control y escribe
  «CUPS CORRECTO» en el certificado.
- La **memoria descriptiva** del MTD, partida en renglones que caben en el
  impreso. Si en la marca y modelo ya escribes la potencia, no la repite detrás.

La **plaza y la planta** se escriben en los cuatro sitios donde hacen falta: el
emplazamiento del MTD, la dirección del punto de suministro del CIE, el
emplazamiento de la autorización y la memoria descriptiva.

---

## Antes de firmar, revisa siempre

La aplicación rellena, no decide. Estas tres cosas conviene mirarlas:

1. **Que el CIE diga COMPLETADO.** Si sale «CIE INCOMPLETO», abre el `CIE.xls`
   de la carpeta y busca las celdas que dicen «FALTAN DATOS».
2. **Los avisos** que salen en pantalla al generar, sobre todo el de caída de
   tensión.
3. **Las casillas de la solicitud de inscripción**, que van premarcadas con la
   documentación habitual (tasa, tarifa EICI, MTD, CIE, dossier, contrato de
   mantenimiento y autorización). Si en un expediente no aportas alguna, hay que
   desmarcarla a mano en el PDF.

---

## Configuración

La pestaña **Configuración** guarda los datos de la empresa instaladora y lo que
se pone en cada impreso.

### Varias empresas

Se pueden tener varias y elegir cuál firma cada expediente: una pestaña por cada
una, arriba del bloque de datos.

- **Añadir otra empresa** abre una en blanco.
- **Duplicar esta** la copia entera. Es lo que más se usa: dos empresas del mismo
  instalador se diferencian en tres o cuatro campos.
- **Borrar esta** quita la que tengas abierta. La última no se puede borrar, y
  los expedientes ya hechos no se tocan: cada uno guarda con qué empresa se hizo.

Con una sola empresa no aparece nada de esto, que es como estaba antes.

Para elegir con cuál se firma, arriba del formulario sale **Empresa
instaladora**. Solo aparece si tienes más de una.

Los **valores técnicos por defecto** se guardan desde la pantalla principal:
ajusta el apartado «Conductor y protecciones» a lo que instalas habitualmente y
pulsa **Guardar estos valores como predeterminados**. Se tocan en un solo sitio
y ves el efecto en el cálculo al momento.

Todo se escribe en `config.json`.

## Cuando el cliente tiene que rellenar algo

El anexo de inspección periódica del garaje pide datos de la comunidad de
propietarios que muchas veces no tienes en el momento. **Déjalos en blanco y
genera igual**: el anexo sale con los datos del cliente y de la instalación ya
puestos, y en los huecos que faltan aparece **en gris lo que hay que escribir
ahí**, para que el cliente lo complete desde el PDF en su casa.

Avísale de que borre el texto gris al escribir encima. Si no lo borra, se imprime
tal cual. La aplicación te lo recuerda al generar.

## Si algo no responde

Si ves un aviso rojo diciendo que se ha perdido el contacto con el programa, es
que se ha cerrado la ventana negra. Vuelve a abrir `iniciar.bat` y pulsa
**Reintentar**. No se pierde nada de lo que hubieras escrito.

---

## Detalles técnicos

- `nucleo.py` — cálculos y relleno de los PDF.
- `cie_libreoffice.py` — camino antiguo, solo si activas `cie_con_libreoffice`. **No se ejecuta
  con el Python normal**, sino con el que trae LibreOffice, que es el único que
  tiene las librerías UNO.
- `cie_pdf.py` — dibuja el CIE sobre el impreso, sin LibreOffice.
- `herramientas/` — preparación del CIE. Solo se usa si cambia el impreso oficial.
- `empaquetar/` — cómo hacer el instalador y cómo firmarlo para vender.
- `servidor.py` — servidor local en el puerto 8123.
- `web\` — la interfaz.
- `plantillas\` — los seis impresos oficiales en blanco. **No los toques**;
  si cambia un impreso oficial, hay que revisar el mapa de campos de `nucleo.py`.

### El CIE ya no necesita LibreOffice

El impreso oficial del CIE es un libro de cálculo que calcula por fórmula tres
cosas: el **identificador del certificado**, el aviso **FALTAN DATOS /
COMPLETADO** y la **comprobación del CUPS**. Antes hacía falta LibreOffice para
que esas fórmulas se recalcularan.

Ahora las tres están reescritas en Python, en `cie_pdf.py`, y los datos se
dibujan encima de `plantillas/CIE_base.pdf`, que es el impreso en blanco
exportado una sola vez. El sitio exacto de cada dato está en
`plantillas/cie_mapa.json`.

Comprobado contra el camino antiguo: **misma página, mismo contenido, mismas
753 palabras** en el mismo sitio. Y se genera en dos segundos en vez de ocho.

Si algún día cambia el impreso oficial, se vuelve a preparar con:

```
"C:\Program Files\LibreOffice\program\python.exe" herramientas/mapear_cie.py
python herramientas/posiciones_cie.py
```

Eso sí necesita LibreOffice, pero **solo en tu ordenador y solo esa vez**. Si
hiciera falta volver al camino antiguo, se pone `"cie_con_libreoffice": true` en
`config.json`.

### Dónde coloca cada dato

Tres detalles del impreso que no son evidentes y están resueltos en el código:

- En la página 4 del MTD, un punto de recarga **no va en la primera fila libre**,
  que pertenece al bloque «Grado de electrificación / Básica», sino en el bloque
  **«Otras instalaciones»**, que empieza en la fila 26.
- En la página 2 del anexo IVE los **nombres de campo del PDF no coinciden con
  la columna sobre la que están**. El campo llamado «Tipo de instalación» es en
  realidad la longitud, el llamado «Intensidad máxima admisible» es la caída de
  tensión máxima, y así con cinco columnas. Está mapeado por posición.
- PyMuPDF **no borra un campo** poniéndole texto vacío, así que los campos que la
  plantilla trae rellenos se vacían escribiendo directamente en el objeto del PDF.

### Sobre los esquemas de la ITC-BT-52

El desplegable trae los **ocho** esquemas oficiales (1a, 1b, 1c, 2, 3a, 3b, 4a,
4b), no solo los dos habituales. Recordatorio del Acta XII del GTREBT: con
esquema 2, 3a, 3b, 4a o 4b **cada punto de recarga es un expediente
independiente**; con 1a, 1b o 1c van todos en uno.
