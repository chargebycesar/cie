# Llevar la aplicación a otro repositorio de GitHub

Ocho pasos. El único que se puede perder por el camino es el primero, así que
ése va antes que nada.

## 1 · Guarda tus datos ANTES de tocar nada

Abre la aplicación como la usas ahora y, en **Configuración › Copia de
seguridad**, pulsa **Descargar copia**. Te baja un `boletines-irve-copia.json`
con tus empresas, tus valores por defecto y el historial de expedientes.

Esto importa de verdad: **tus datos no están en el repositorio**, están dentro
del navegador, atados a la dirección de la página.

| Si el repositorio nuevo es... | Qué pasa con tus datos |
|---|---|
| De la **misma** cuenta de GitHub | Siguen ahí: la dirección `tu-usuario.github.io` es la misma |
| De **otra** cuenta | **Se quedan atrás.** Sin la copia del paso 1 no se recuperan |

Hazla igualmente. No cuesta nada y el día que falle es el día que no la tienes.

## 2 · Crea el repositorio nuevo

En [github.com/new](https://github.com/new):

- ponle nombre (por ejemplo `boletines-irve`),
- déjalo **público** -las páginas gratis lo exigen-,
- **no** marques añadir README, ni .gitignore, ni licencia. Tiene que quedar
  vacío del todo.

## 3 · Descomprime esta carpeta

Donde quieras, pero **no dentro de OneDrive**: Git y OneDrive se pelean y
acabas con archivos a medias.

## 4 · Doble clic en `publicar.bat`

Te va a preguntar, una sola vez:

- tu nombre y tu correo (es lo que firma los cambios en Git),
- la dirección del repositorio que acabas de crear.

Y sube. Antes de subir comprueba que no se cuela ningún dato personal: si
encuentra un DNI, un CIF, un CUPS, un correo o un móvil que no toque, se para y
no sube nada.

Si no tienes Git instalado, el script te lo dice y te da el enlace.

## 5 · Enciende la página

Esto es lo único que hay que hacer a mano en GitHub, y una sola vez. En el
repositorio nuevo:

**Settings › Pages › Source: Deploy from a branch**, rama **`main`**, carpeta
**`/docs`**, y **Save**.

## 6 · Espera un par de minutos

GitHub tarda eso en publicar. Luego abre:

```
https://TU-USUARIO.github.io/TU-REPOSITORIO/
```

## 7 · Restaura tus datos

En la aplicación nueva: **Configuración › Copia de seguridad › Restaurar
copia**, y le das el `boletines-irve-copia.json` del paso 1.

## 8 · Comprueba que está todo

- Sale tu empresa en Configuración -y las demás, si tienes varias-.
- En Expedientes está tu historial.
- Genera un expediente de prueba y ábrelo: los siete documentos, con tus datos.

---

## Si prefieres conservar el historial de cambios

Lo de arriba empieza de cero en el repositorio nuevo, que para esto vale. Si
quieres llevarte los commits, no uses este ZIP: desde tu carpeta de siempre,

```bash
git remote set-url origin https://github.com/TU-USUARIO/TU-REPOSITORIO.git
```

```bash
git push -u origin main
```

y sigue desde el paso 5.

## Qué NO va en este ZIP, y por qué

- **`config.json`** — tus datos de empresa para la versión de escritorio. Al
  lado tienes `config.ejemplo.json`: cópialo con ese nombre y rellénalo, si es
  que usas la versión de escritorio. La del navegador no lo necesita.
- **`fuente/`** — los impresos tal como llegaron de Industria. Llevan dentro
  datos de otros trabajos y no deben salir de tu ordenador. Solo hacen falta si
  algún día hay que rehacer una plantilla desde cero.
- **`salida/`** — expedientes ya generados, con datos de clientes reales.
- **`node_modules/`** — se rehace con `npm install`, y solo para las
  comprobaciones de `COMPROBAR.md`.
- **El historial de Git** — para que el repositorio nuevo empiece limpio.

## Qué necesita el servidor

Nada. Son archivos estáticos: GitHub Pages los sirve y la aplicación funciona
entera dentro del navegador. No hay base de datos, ni claves, ni nada que
configurar. Por eso también vale cualquier otro sitio que sirva archivos
estáticos, apuntando a la carpeta `docs/`.
