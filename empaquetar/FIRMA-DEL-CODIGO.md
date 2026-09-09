# Firmar el programa para poder venderlo

## Lo que yo no puedo hacer

**No puedo comprarte el certificado ni firmar en tu nombre.** Un certificado de
firma de código se emite a nombre de una empresa concreta, y para conseguirlo hay
que pagarlo y pasar una verificación de identidad: escrituras de la sociedad,
CIF, una llamada de comprobación y, en los de tipo EV, recibir físicamente una
llave USB. Eso lo tienes que hacer tú como administrador de Bufala Tech.

Lo que sí está hecho: **todo el empaquetado y el paso de firma están montados**.
Cuando tengas el certificado, firmar es un comando.

---

## Qué pasa si no firmas

Al abrir el instalador, Windows enseña una pantalla azul que dice
«Windows protegió su PC» y esconde el botón de instalar detrás de
«Más información». Muchos compradores no pasan de ahí. Con firma, esa pantalla
desaparece (con el certificado normal tarda unas semanas en desaparecer del todo,
mientras Microsoft acumula reputación; con el EV desaparece desde el primer día).

---

## Qué comprar

| Tipo | Precio orientativo al año | Aviso de Windows | Qué necesitas |
|---|---|---|---|
| **OV** (validación de organización) | 250 a 400 € | Desaparece en semanas, según descargas | CIF y verificación de la empresa |
| **EV** (validación extendida) | 400 a 700 € | Desaparece desde el primer minuto | Lo anterior más una llave física USB |

Desde junio de 2023 **todos los certificados de firma de código exigen que la
clave esté en un dispositivo físico o en un servicio de firma en la nube**. Ya no
se descarga un `.pfx` sin más. Los proveedores suelen ofrecer las dos opciones.

Emisores habituales: Sectigo, DigiCert, GlobalSign, Certum. Los revendedores
salen bastante más baratos que comprar directamente.

**Mi recomendación**: empieza por el **OV**. Es la mitad de precio y, para vender
a instaladores que te conocen o que te compran tras una demostración, el aviso de
las primeras semanas no es un problema real. Pasa al EV solo si vendes por
internet a desconocidos.

---

## Cómo firmar, una vez lo tengas

Si el proveedor te da un `.pfx` (certificados antiguos o de prueba):

```powershell
.\empaquetar\construir.ps1 -Firmar -Certificado C:\ruta\bufalatech.pfx -ClaveCertificado "tu-clave"
```

Si te da una llave USB o firma en la nube, el certificado ya está en el almacén
de Windows y se firma por nombre en vez de por fichero:

```powershell
signtool sign /fd SHA256 /n "BUFALA TECH SL" /tr http://timestamp.digicert.com /td SHA256 "BoletinesIRVE-1.0.0-instalador.exe"
```

Para no escribir la contraseña cada vez, déjala en el entorno:

```powershell
$env:BOLETINES_PFX = "C:\ruta\bufalatech.pfx"
$env:BOLETINES_PFX_PASS = "tu-clave"
```

### Por qué el sello de tiempo importa

El `/tr` pone un **sello de tiempo**. Sin él, el día que caduque el certificado
dejarían de valer todas las copias que ya vendiste. Con él, siguen siendo válidas
para siempre, porque queda constancia de que se firmaron cuando el certificado
estaba vigente. No lo quites nunca.

---

## Antes de vender, además de la firma

- **Condiciones de uso** que dejen claro que la autoría técnica y la
  responsabilidad del expediente son del instalador habilitado que firma, y que
  el programa es una herramienta. Sin esto no deberías vender.
- **RGPD**: los expedientes llevan DNI, CUPS y domicilios de terceros. Al vender
  el programa pasas a ser encargado del tratamiento. Ayuda mucho que los datos no
  salgan del ordenador del cliente, que es como está hecho, pero hace falta el
  documento.
- **Derechos sobre los impresos oficiales** que van dentro del paquete. Conviene
  confirmarlo con cada administración antes de redistribuirlos.
