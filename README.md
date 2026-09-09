# Boletines IRVE · Comunidad de Madrid

Genera el expediente completo de un punto de recarga de vehículo eléctrico
rellenando un solo formulario: el CIE, la memoria técnica de diseño, el anexo de
la ITC-BT-52, el esquema unifilar, la solicitud de inscripción, la autorización
del titular y, si hace falta, el anexo de inspección del garaje.

**Todo ocurre en tu navegador.** Los datos del cliente no se suben a ningún
sitio: los PDF se generan en tu ordenador y se descargan de ahí. La página solo
sirve el programa, igual que serviría un folleto.

---

## Subirla a GitHub y publicarla

Doble clic en **`publicar.bat`**. Eso es todo.

La primera vez te pregunta tu nombre y tu correo, te abre GitHub para que crees
el repositorio y te pide su dirección. Las siguientes solo te pregunta qué has
cambiado y sube.

Antes de subir nada comprueba que no se cuela ningún dato personal: si encuentra
un DNI, un CIF, un CUPS, un correo o un móvil que no sea tuyo ni del expediente,
**se para y no sube**. El repositorio es público y lo que se sube una vez se
queda en el historial aunque luego lo borres.

### Lo único que hay que hacer a mano, y una sola vez

Cuando el script termine la primera subida te lo recuerda: en el repositorio,
**Settings › Pages**, en *Source* eliges **Deploy from a branch**, rama `main`,
carpeta **`/docs`**, y Save. En un par de minutos está en
`https://TU-USUARIO.github.io/TU-REPOSITORIO/`.

Hace falta tener [Git](https://git-scm.com/download/win) instalado. Si no lo
está, el script te lo dice y te da el enlace.

### Si prefieres hacerlo a mano

```bash
git add .
```

```bash
git commit -m "lo que hayas cambiado"
```

```bash
git push
```

Comprobando antes, siempre:

```bash
python herramientas/rastrear.py docs/plantillas/*.pdf
```

---

## Qué hay en cada carpeta

| Carpeta | Qué es |
|---|---|
| `docs/` | La aplicación que se publica. Es la que se usa. |
| `docs/plantillas/` | Los impresos oficiales y el mapa del CIE. **Copia única**: la versión de escritorio lee de aquí también, para que no haya dos que se desincronicen. |
| `fuente/` | Los impresos tal como llegaron y el `CIE.xls` original. **No se sube nada de aquí**: llevan dentro los datos de otros trabajos y tu NIF. Se queda en tu ordenador por si hay que rehacer una plantilla. |
| `nucleo.py` | El mismo motor escrito en Python. Se conserva porque es el que valida al del navegador: `herramientas/comparar.py` genera el expediente por los dos caminos y compara campo por campo. |
| `servidor.py`, `web/` | La versión de escritorio. **Su pantalla se quedó atrás** (le faltan campos que sí están en `docs/`). El motor sí está al día. Usa la del navegador. |
| `config.json`, `prueba.json` | Tus datos y un expediente de prueba. **No se suben al repositorio.** Junto a ellos están `config.ejemplo.json` y `prueba.ejemplo.json`, que sí, con los datos en blanco. |
| `publicar.bat` | Sube la aplicación a GitHub. Doble clic. |
| `herramientas/` | Preparación de los impresos y comprobaciones. Solo se usa si cambia un impreso oficial. |
| `empaquetar/` | Instalador y firma de código, por si algún día se vende. |
| `CONSEJO-multicomunidad.md` | Cómo llevar esto a las otras comunidades. |

---

## Detalles técnicos

Sin dependencias que instalar ni paso de compilación. La página carga
[pdf-lib](https://pdf-lib.js.org/) y [JSZip](https://stuk.github.io/jszip/) desde
un CDN y el resto son cuatro módulos de JavaScript:

- `motor.js` — cálculos eléctricos, comprobaciones y el mapa de campos de cada impreso.
- `relleno.js` — rellena los impresos con formulario.
- `cie.js` — dibuja el CIE sobre el impreso en blanco, con las tres fórmulas del
  libro oficial reescritas: el identificador del certificado, el aviso
  FALTAN DATOS / COMPLETADO y la comprobación del CUPS.
- `app.js` — la pantalla.

El motor de JavaScript se comprobó contra el de Python sobre el mismo
expediente: **cero diferencias** en los 1.852 campos de los cuatro impresos con
formulario, y las mismas 751 palabras en el CIE. La comprobación se repite con:

```bash
python herramientas/comparar.py
```

### El esquema unifilar

Se rellena solo, con la línea que has configurado: número de conductores,
sección, material y aislamiento en la derivación individual, y el calibre del
magnetotérmico y del diferencial con su sensibilidad y su clase. Abajo van el
titular, el emplazamiento, la empresa instaladora y la fecha.

### Los dos botones del MTD

El MTD trae dos botones, **Limpiar Campos** e **Imprimir**. Mirando el archivo
original por dentro:

- **Limpiar Campos** es un borrado de formulario, y respeta cuatro campos:
  año, código de impreso, día y mes.
- **Imprimir** no es una macro ni hace nada especial. Su acción es
  `/S /Named /N /Print`, que es **literalmente el comando Imprimir del visor**,
  lo mismo que pulsar Ctrl+P.

Lo que sí importa es otra cosa: el impreso marca **trece campos como «no
imprimir»**, que son los dos botones de cada una de las seis páginas y el aviso
amarillo de la cabecera. Por eso al imprimir no salen. Y el MTD que aprobó la
OCA, mirado por dentro, tampoco los lleva **y conserva sus campos de formulario**,
es decir, no está aplanado.

Así que la aplicación saca **dos versiones del MTD**:

| Archivo | Qué es |
|---|---|
| `MTD - Memoria Tecnica de Diseno.pdf` | Sin los botones ni el aviso, con los campos de formulario. Es como el que aprobó la OCA. |
| `MTD - ... (version impresa).pdf` | Lo mismo pero aplanado: exactamente lo que sale al pulsar Imprimir y elegir «imprimir a PDF». Los datos quedan fijos. |

Ya no hace falta pulsar el botón: los dos salen hechos. Usa el que te pidan.

### Los impresos no venían en blanco

Los PDF de partida no eran impresos vacíos: eran expedientes ya rellenados de
otros trabajos, con los campos borrados por encima. Por dentro seguían llevando,
invisible al abrirlos pero recuperable con cualquier extractor de formularios:

- el nombre, el DNI, la dirección, el teléfono y el correo de **clientes de
  otras instalaciones**, y los datos de **otra empresa instaladora**;
- campos de formulario que no colgaban de ninguna página, de un impreso
  anterior distinto;
- el dibujo del texto viejo, que sobrevive aunque se cambie el valor del campo.

Todo eso salía dentro de cada documento generado. Se limpia una sola vez, sobre
las plantillas:

```bash
python herramientas/limpiar_plantillas.py
```

Y se comprueba, tanto en las plantillas como en lo que se entrega:

```bash
python herramientas/rastrear.py docs/plantillas/*.pdf salida/*/*.pdf
```

Tres cosas que se aprendieron limpiándolos, por si hay que repetirlo con otro
impreso:

- **No se puede borrar la clave `/AP` de un campo.** Queda escrito un `null`
  literal y a partir de ahí el visor ya no sabe redibujarlo: el impreso acepta
  valores pero sale en blanco. Lo que sí funciona es dejar el dibujo vacío.
- **El valor no siempre está en el recuadro.** En los impresos con nombres del
  tipo `topmostSubform[0].Page1[0].Campo[0]` vive en un campo padre. Pero si se
  le pone valor al recuadro suelto, que es solo el dibujo, el impreso deja de
  funcionar. El valor solo va donde hay nombre de campo.
- **El AcroForm no se puede rehacer de cero.** Ahí vive `/DR`, el catálogo de
  fuentes. Sin él los campos se quedan mudos. Y en algunos impresos está escrito
  dentro del catálogo en vez de apuntar a un objeto aparte.

### Comprobar antes de subir

```bash
python herramientas/rastrear.py docs/plantillas/*.pdf salida/*/*.pdf
```

Reconoce DNI, NIE, CIF, CUPS, correos y móviles por su forma, mira también lo
que no se ve al abrir el PDF, y descuenta los que sí tocan: los tuyos y los del
expediente. Si sale algo, no subas nada hasta limpiarlo.

### Dos cosas que costaron encontrar

El **anexo IVE** venía con el diccionario de formulario roto, apuntando a un
objeto que no existe, así que las librerías de navegador no veían ningún campo.
Se reconstruye con `herramientas/reparar_anexo.py`, que ya está aplicado.

Las **casillas** de estos impresos usan el estado «Sí» en vez del habitual
«Yes». PyMuPDF no las marca con el atajo de siempre; pdf-lib sí.
