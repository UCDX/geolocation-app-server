# Close user app

## Requisitos

### Dependecias a instalar

Para instalar las dependencias utilice el comando: 

`pip install -r requirements.txt`

### Variables de entorno

Es importante configurar las siguientes variables de entorno

```
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=
MYSQL_HOST=
MYSQL_PORT=
ENV=
DIST_TRESHOLD=
```

* DIST_TRESHOLD: distancia mínima (en metros) para detectar a otro usuario.
* ENV: Entonrno de ejecución. Opciones: `production` o `development`

## Extra

Ruta para testear la geolocalizacion: `/close_users`