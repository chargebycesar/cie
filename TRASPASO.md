# Traspaso del proyecto

Esto es lo que hay que saber para seguir con la aplicación en otro ordenador, o
para que la coja otra persona. El detalle técnico está en `README.md`; cómo se
usa, en `LEEME.md`; qué comprobar antes de subir un cambio, en `COMPROBAR.md`.

## Qué es

Una aplicación que genera el expediente completo de un punto de recarga de
vehículo eléctrico para la Comunidad de Madrid a partir de un solo formulario:
CIE, MTD, anexo de la ITC-BT-52, esquema unifilar, solicitud BT-1134F1,
autorización del titular y, si hace falta, el anexo de inspección del garaje.

Funciona **entera dentro del navegador** (`docs/`, publicada en GitHub Pages).
`nucleo.py` es el mismo motor escrito en Python: no se usa para trabajar, sirve
para comprobar que el del navegador sigue dando exactamente lo mismo.

## Los dos paquetes

| Archivo | Qué lleva | Para qué |
|---|---|---|
| `boletines-madrid-completo.zip` | El proyecto entero, con su historial de Git, tu configuración y los impresos originales | Seguir trabajando tú, en otro ordenador |
| `boletines-madrid-publico.zip` | Solo lo que ya está publicado en GitHub | Dárselo a alguien |

### Lo que NO va en ninguno de los dos

- `salida/` — expedientes ya generados. Llevan datos de clientes reales.
- `node_modules/` — 25 MB que se rehacen con `npm install`.
- `__pycache__/` — lo rehace Python solo.

### Lo que va SOLO en el completo

- `config.json` y `prueba.json` — los datos de tu empresa y del técnico.
- `fuente/` — los impresos tal como llegaron de Industria, antes de limpiarlos.
  Llevan dentro datos de otros trabajos: otro instalador, otros clientes. Por
  eso están fuera del repositorio y por eso no van en el paquete público.
- `.git` — el historial, 16 commits. Con él, `publicar.bat` sigue funcionando
  desde el ordenador nuevo sin volver a configurar nada.

## Para arrancarlo en otro ordenador

1. Descomprimir donde sea (no en una carpeta sincronizada con OneDrive: Git y
   OneDrive se pelean).
2. Instalar Python 3.11 o más nuevo y Node 18 o más nuevo.
3. Dentro de la carpeta:

   ```bash
   pip install -r requisitos.txt
   npm install
   ```

4. Para trabajar, doble clic en `iniciar.bat`. Para publicar un cambio, doble
   clic en `publicar.bat`.

Si has cogido el paquete completo, el `git push` pedirá las credenciales de
GitHub la primera vez. Eso lo hace el usuario; yo no manejo sus claves.

## Antes de dar nada por bueno

```bash
npm run comprobar   # 18 casos límite, ninguno debe romper
npm run comparar    # los dos motores tienen que dar lo mismo, campo por campo
python herramientas/rastrear.py   # que las plantillas no lleven datos de nadie
```

Las tres tienen que salir limpias. Están explicadas en `COMPROBAR.md`.

## Las trampas que costaron tiempo

Están todas contadas en el `README.md`, pero conviene saber que existen antes de
tocar nada:

- **Los impresos oficiales no venían en blanco.** Traían datos de otros trabajos
  dentro. `herramientas/limpiar_plantillas.py` los deja limpios, en doce pasos
  que van en ese orden por algo.
- **El gris de las leyendas va solo en el dibujo, nunca en el `/DA`.** Si se
  pone en los dos, lo que escriba el cliente encima sale gris.
- **Hay recuadros guardados del revés** (`y1 < y0`). MuPDF los endereza solo y
  otros visores no: el campo sale en blanco solo en el ordenador del cliente.
- **El MTD tiene 1 631 campos y 1 611 sin apariencia**, así que `removeField()`
  de pdf-lib revienta. Hay que quitar los widgets a mano.
- **La casilla del CIE no se marca con `/Yes`**, sino con `/S#ED`.
- **GitHub Pages cachea.** Por eso `publicar.py` sella cada archivo con `?v=`
  antes de subirlo.
