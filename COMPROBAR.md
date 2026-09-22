# Comprobar que todo sigue bien

Antes de subir un cambio conviene pasar estas dos comprobaciones. La primera vez
hay que instalar la librería que usan:

```bash
npm install
```

## 1. Casos límite

```bash
npm run comprobar
```

Pasa el motor por dieciocho situaciones incómodas: formulario vacío, sin CUPS,
NIF mal, longitud cero, trifásico a 400 V, aluminio, potencia mayor que la
protección, texto con emojis o comillas tipográficas, observaciones larguísimas
y configuración sin datos de empresa.

**Ninguna debe romper.** Si alguna sale como ROMPE o FALLO, hay trabajo.

## 2. Que el navegador y Python siguen dando lo mismo

```bash
npm run comparar
```

Genera el mismo expediente por los dos caminos y compara campo por campo. Tiene
que terminar diciendo **«Los dos motores dan exactamente lo mismo»**.

Si tocas la lógica de uno de los dos motores y se te olvida el otro, esto lo
canta enseguida.

## Qué mirar a ojo, de vez en cuando

Genera un expediente de verdad y comprueba:

- El CIE dice **COMPLETADO** y trae su identificador.
- El MTD sale **sin los botones** ni el aviso amarillo de la cabecera.
- El anexo del garaje, si dejas la comunidad en blanco, deja los huecos **en
  gris** con la pista de qué escribir.
- La fecha lleva el **mes en mayúsculas**.
- Los campos ya escritos tienen **fondo blanco**; los que faltan, sombreado.
