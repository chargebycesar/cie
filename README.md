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

### Dos cuentas de GitHub

Windows guarda **una sola** contraseña de GitHub y Git la reutiliza para todos
los repositorios. Con dos cuentas, subir a un repositorio de la segunda falla con
un 403 aunque el repositorio sea tuyo: entra con la primera.

Se arregla metiendo el usuario en la dirección del repositorio, y así Windows
guarda una contraseña por cada cuenta:

```bash
git remote set-url origin https://TU-USUARIO@github.com/TU-USUARIO/TU-REPOSITORIO.git
```

`publicar.py` reconoce ese error, dice con qué cuenta estás entrando y de quién
es el repositorio, y se ofrece a cambiarlo él.

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

## Cómo se usa

La primera vez, en **Configuración**: los datos de tu empresa. Se guardan en ese
navegador y no hay que volver a escribirlos.

Después, por cada obra: cliente, plaza y planta, metros de línea y CUPS. Lo demás
viene puesto. Pulsas **Generar documentos** y te descargas el ZIP.

### El código postal

Un municipio puede tener muchos códigos postales: Madrid tiene más de
doscientos, y hasta la calle de Alcalá cambia de código a mitad. Por eso la
aplicación **los recuerda por calle**, no por localidad. La segunda instalación
del mismo pueblo, en otra calle, no hereda el código de la primera: la casilla
se queda vacía, que es lo correcto.

Si no lo sabes, el botón **Buscar** que hay junto a la casilla se lo pregunta a
[CartoCiudad](https://www.cartociudad.es/), el callejero oficial del Instituto
Geográfico Nacional, que lo da por calle y número. Si tu portal no está, coge el
más cercano de la calle y te avisa. Y si la calle cruza dos códigos postales, te
enseña los dos para que elijas el tuyo.

La búsqueda está acotada a la **provincia de Madrid**, que es para donde hace
boletines esto. Sin acotar, una calle con nombre común devuelve resultados de
media España. El día que haga falta otra comunidad se quita de `docs/cp.js`.

El resultado se contrasta **por calle y por municipio a la vez**, porque ninguna
de las dos cosas basta sola. La misma calle existe en medio país: buscando
«Calle Real» en Rivas-Vaciamadrid, el callejero contesta con la de Crémenes, en
León. Y dentro de un mismo municipio hay calles que se parecen: buscando «Mayor»
ofrece «Mayorga» y «Miguel Mayor», que son otras calles con otro código. Si la
calle existe pero en otro sitio, te lo dice en vez de darte un código de allí.

**Es lo único de toda la aplicación que sale de tu ordenador**, y por eso hay que
pulsar el botón: no se consulta nada solo. Lo que sale es la dirección —tipo de
vía, nombre, número, localidad y provincia—, nunca el nombre, el DNI, el teléfono
ni el correo de nadie. Si no hay red, o el servicio no contesta, se escribe a
mano y no pasa nada más.

### Copia de seguridad

Lo tuyo vive en el navegador. Si cambias de ordenador, borras los datos de
navegación o usas otro navegador, lo pierdes. En **Configuración** tienes
**Descargar copia**, que te guarda en un archivo los datos de empresa, los
valores por defecto, los códigos postales y el historial. Con **Restaurar copia**
lo devuelves.

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
| `publicar.bat` | Sube la aplicación a GitHub. Doble clic. Antes de subir pone el sello de versión y comprueba que no se cuela ningún dato personal. |
| `docs/plantillas/campos.json`, `docs/plantillas/img/` | Los huecos de cada impreso (dónde están, qué tamaño tienen, qué pone al lado y si los rellena la aplicación) y la imagen de cada página, para poder pincharlos sobre la hoja desde Configuración. |
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
- `cp.js` — el código postal: la memoria por calle y la consulta al
  callejero oficial.
- `app.js` — la pantalla.

El motor de JavaScript se comprobó contra el de Python sobre el mismo
expediente: **cero diferencias** en los 1.852 campos de los cuatro impresos con
formulario, y las mismas 751 palabras en el CIE. La comprobación se repite con:

```bash
python herramientas/comparar.py
```

### Lo que pone en cada documento se elige sobre el propio documento

En **Configuración**, una pestaña por impreso, y dentro **la hoja tal como va a
salir**. Cada hueco enseña lo que va a decir y de dónde sale:

| Color | Quién lo pone |
|---|---|
| Azul | El expediente de cada cliente |
| Ámbar | Lo que tienes puesto por defecto |
| Verde | Lo que has cambiado tú |
| Punteado | Vacío: pincha y escribe |

Se pincha cualquiera y se cambia ahí mismo, con un solo botón: **Guardar como
predeterminado**. Hay buscador -que encuentra por lo que pone al lado, por el
nombre del campo, por el nombre del ajuste o por lo que va a salir escrito- y
zoom al 150 y 200 % para los impresos de letra pequeña. El CIE, que no es un
formulario sino una hoja de cálculo, sigue por celdas (A28, B43...).

Antes esto estaba **en tres sitios**: una rejilla de valores con nombre, una
lista de campos sueltos y la hoja. Ninguno de los tres enseñaba el resultado, y
los tres se pisaban entre sí.

#### Filas donde solo puede ir marcada una

«Puesta a tierra: Picas / Placas / Mallas» es una fila de esas. Emplazamiento
-Planta Baja, Entresuelo, 1º Sótano, Cada 6 Plantas, En Cada Planta- es otra, y
Ubicación otra más.

En el impreso son huecos de texto sueltos donde se escribe una X, así que nada
impedía que salieran dos marcadas: la X de Picas estaba escrita a pelo en el
mapa, y si además añadías una X en Mallas, **el documento salía con las dos** y
no había forma de verlo hasta abrir el PDF.

Ahora la fila es una sola cosa. Al elegir una opción, el motor escribe la marca
en la suya y **vacía las demás del grupo**, siempre: tanto si la eliges en la
pantalla como si escribes una X a mano en otra casilla de la fila. Los grupos se
declaran en la configuración (`opciones_excluyentes`), no en el código, así que
se puede añadir uno nuevo sin tocar el programa.

Los nombres de las opciones están mirados uno a uno contra el impreso: en el MTD
los rótulos son dibujo, no texto, y no se pueden sacar solos.

#### Cómo sabe la pantalla a qué hueco va cada ajuste

No lleva una lista a mano -se quedaría vieja en cuanto alguien tocara el mapa
del impreso-. Le pregunta al motor: pone una marca imposible en cada valor, arma
el documento y mira en qué hueco ha salido. Con las casillas no vale una marca,
así que las apaga y mira cuál cambia.

Por eso «Presupuesto, materiales» se cambia en un sitio y sale en los dos huecos
que lo llevan, sin que nadie tenga que acordarse de que son dos.

Los huecos y las imágenes salen de `herramientas/indice_campos.py`, que recorre
cada impreso, dibuja cada página a imagen y apunta de cada campo dónde está y
qué tamaño tiene, su página, el texto que tiene al lado y si lo rellena la
aplicación. Hay que volver a ejecutarlo si Industria cambia un impreso.

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

Así que el MTD sale **sin los botones ni el aviso y aplanado**: exactamente lo
que saldría al pulsar Imprimir y elegir «imprimir a PDF». Los datos quedan
fijos y ya no hay formulario. No hace falta pulsar nada.

Al aplanar apareció un detalle del impreso: **el dibujo de un campo vacío no es
transparente, es un rectángulo blanco**. Mientras es un formulario da igual,
porque el visor lo redibuja; pero al aplanarlo queda estampado y se come las
líneas de las tablas, que salen a trozos. Como un campo sin texto no aporta
nada al documento impreso, se quita entero antes de aplanar.

Y otro: tres campos de la cabecera oficial («Dirección General de», «Etiqueta
de Registro», «Comunidad de Madrid») traen el dibujo sin declarar `/Type
/XObject /Subtype /Form`. Como campos se ven igual, pero al aplanar
desaparecían. Se completa en `herramientas/limpiar_plantillas.py`.

### De dónde salen los impresos

El MTD es el oficial, descargado tal cual de la sede de la Comunidad de Madrid:

- [Tramitación de instalaciones eléctricas](https://sede.comunidad.madrid/autorizaciones-licencias-permisos-carnes/tramitacion-instalaciones-electricas/presencial)
- [Modelo de Memoria Técnica de Diseño](https://gestiona7.madrid.org/i012_impresos/run/j/VerImpreso.icm?CDIMPRESO=IMPRE2722)
- [Modelo de certificado de instalación (el XLS del CIE)](https://gestiona7.madrid.org/i012_impresos/run/j/VerImpreso.icm?CDIMPRESO=1134FO1)

Si Industria cambia un impreso, se descarga de ahí, se pasa por
`herramientas/limpiar_plantillas.py` y se comprueba con
`herramientas/comparar.py` que los campos siguen llamándose igual.

### Los impresos no venían en blanco

Los PDF de partida no eran impresos vacíos: eran expedientes ya rellenados de
otros trabajos, con los campos borrados por encima. Por dentro seguían llevando,
invisible al abrirlos pero recuperable con cualquier extractor de formularios:

- el nombre, el DNI, la dirección, el teléfono y el correo de **clientes de
  otras instalaciones**, y los datos de **otra empresa instaladora**;
- campos de formulario que no colgaban de ninguna página, de un impreso
  anterior distinto;
- el dibujo del texto viejo, que sobrevive aunque se cambie el valor del campo.

Todo eso salía dentro de cada documento generado. **El MTD ya no es ese: se ha
sustituido por el oficial de Industria**, que está virgen de verdad (solo trae
sus siete campos de cabecera y aviso legal). Los demás se limpian una sola vez,
sobre las plantillas:

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

### Las leyendas grises no tiñen lo que escribe el cliente

En el anexo del garaje hay huecos que rellena el cliente, y salen con una
leyenda en gris diciendo qué va en cada uno. El problema: al escribir encima,
lo suyo salía también en gris, como si fuera otra leyenda.

Se arregla separando las dos cosas. El **dibujo** del campo se genera en gris
—que es lo que se ve— y justo después se le devuelve el negro al campo. El
visor usa el dibujo para enseñarlo y el `/DA` para lo que se teclea dentro, así
que valen los dos a la vez: la leyenda se ve gris y lo que escribe el cliente
sale negro, como el resto del documento. Sin JavaScript dentro del PDF, que no
todos los visores lo ejecutan.

### El recuadro del sello del CIE va vacío

El CIE lleva arriba a la derecha un recuadro de **Sello y fecha EICI**: es donde
firma y sella la EICI, así que sale en blanco. La hoja de cálculo original
escribía ahí «COMPLETADO» o «FALTAN DATOS» para avisarte de si ya podías
imprimir; ese aviso sigue estando, pero **en la pantalla**, junto al documento
generado, no dentro del papel que entregas.

### Cuatro recuadros que salían en blanco

En el anexo del garaje, el NIF del cliente, su domicilio, el domicilio de la
comunidad y el lugar de la firma salían vacíos en algunos visores aunque el
texto estuviera dentro del PDF. El motivo: esos cuatro recuadros vienen con el
**rectángulo del revés** —la esquina de abajo por encima de la de arriba—. La
norma lo permite, pero hay visores que directamente no dibujan ese campo.

Costó dar con ello porque las herramientas de aquí sí los enseñaban: MuPDF los
pone del derecho al leerlos. Se enderezan en
`herramientas/limpiar_plantillas.py`, y de paso el ajuste de la letra toma el
alto en valor absoluto, que con un alto negativo elegía el tamaño mínimo.

### Varias empresas instaladoras

Se puede tener más de una y elegir cuál firma cada expediente. Lo que cambia de
una a otra es el bloque entero -razón social, NIF, registro industrial, el
instalador y su número de certificado-, así que cada una se guarda completa, con
un identificador propio que no cambia aunque le cambies el nombre.

Lo que **no** cambia es el resto del programa: `CFG.empresa` sigue siendo la
empresa elegida en cada momento, y los mapas de los impresos y los dos motores
no se enteran de que hay varias. En Python lo resuelve `_elegir_empresa()` al
cargar la configuración; en el navegador, `prepararEmpresas()` al arrancar.

Los ajustes de antes, con una sola empresa guardada como `empresa` a secas, se
meten en la lista tal cual: no hay que hacer nada.

Mirando un expediente antiguo se trabaja sobre una **copia suelta** de su
empresa, no sobre la de la lista, y Guardar se niega a hacer nada hasta que
vuelves a tus datos de ahora. Si no, abrir un expediente de marzo y darle a
guardar te machacaba la empresa con la de entonces.

### Los expedientes guardan con qué datos se hicieron

Al volver a abrir un expediente de hace meses salía con los datos de empresa de
hoy, así que el documento ya no era el que se entregó. Ahora cada expediente
guarda también la empresa, el instalador y los valores de los impresos que
tenía, y al abrirlo se recuperan. Sale un aviso arriba y un botón para volver a
tus datos de ahora; tu configuración guardada no se toca.

### El sello de versión

El navegador se guarda los `.js` y GitHub Pages le dice que puede quedárselos un
rato, así que después de publicar un arreglo se puede seguir usando la versión
de antes sin enterarse. Por eso `publicar.bat` le pone un `?v=` con la fecha y la
hora a cada módulo antes de subir, con `herramientas/sellar_version.py`. Así cada
publicación trae una dirección distinta y el navegador se la baja.

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
