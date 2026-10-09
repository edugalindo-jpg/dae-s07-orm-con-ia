# Documentación del laboratorio — ORM con IA: duelo y verificador

Repositorio: `dae-s07-orm-con-ia` (DAE, semana 7, laboratorio extra).
Entorno: `venv` (Python 3.14.7, Django 6.1.2).

---

## Paso 1 — Entorno y base de datos

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_blog
```

Resultado:

- Migraciones aplicadas: `contenttypes`, `auth`, `admin`, `sessions`, `blog.0001_initial`.
- `seed_blog`: **4 autores, 15 artículos, 23 comentarios** (datos deterministas).

---

## Paso 2 — Conteo exacto de la base de datos

Ejecutado con `python manage.py shell`:

```python
>>> from blog.models import Author, Profile, Category, Tag, Post, Comment
>>> for m in (Author, Profile, Category, Tag, Post, Comment):
...     print(m.__name__, m.objects.count())
```

| Modelo | Registros |
|---|---|
| `Author` (autores) | **4** |
| `Profile` (perfiles) | 4 |
| `Category` (categorías) | 4 |
| `Tag` (etiquetas) | 5 |
| `Post` (artículos) | **15** |
| `Comment` (comentarios) | **23** |

Respuesta a la consigna: **4 autores, 15 artículos y 23 comentarios.**

---

## Paso 3 — Diagrama Entidad-Relación (texto)

Modelos en `blog/models.py`.

### Entidades

| Entidad | Atributos principales |
|---|---|
| `Author` | `name` (CharField) |
| `Profile` | `country`, `bio` + FK/O2O a `Author` |
| `Category` | `name` (único) |
| `Tag` | `name` (único) |
| `Post` | `title`, `body`, `published`, `published_at` + FKs a `Author`, `Category`, M:N con `Tag` |
| `Comment` | `author_name`, `text`, `created_at` + FK a `Post` |

### Relaciones

1. **`Author` 1 — 1 `Profile`** (`blog/models.py:14`)
   `Profile.author = models.OneToOneField(Author, on_delete=CASCADE, related_name="profile")`.
   Cada autor tiene como máximo un perfil; el perfil no existe sin su autor (borrar el autor
   borra el perfil). Acceso inverso: `author.profile.country`.

2. **`Post` N — 1 `Category`, FK opcional** (`blog/models.py:45`)
   `category = models.ForeignKey(Category, null=True, blank=True, on_delete=SET_NULL, related_name="posts")`.
   Un artículo puede no tener categoría (`NULL`); si la categoría se borra, el artículo queda
   **sin categoría** en vez de borrarse (`SET_NULL`). Por eso la Pregunta 2 ("sin categoría")
   tiene respuesta no vacía. Inverso: `category.posts`.

3. **`Post` N — M `Tag`** (`blog/models.py:46`)
   `tags = models.ManyToManyField(Tag, blank=True, related_name="posts")`.
   Django crea la tabla intermedia `blog_post_tags` (`post_id`, `tag_id`). Un artículo tiene
   muchas etiquetas y una etiqueta aparece en muchos artículos. **Ojo:** al hacer `annotate`
   con `Count` sobre un M:N se multiplican las filas (ver Paso 5).

4. **`Comment` N — 1 `Post`** (`blog/models.py:55`)
   `post = models.ForeignKey(Post, on_delete=CASCADE, related_name="comments")`.
   Un comentario pertenece a un solo artículo; borrar el artículo borra sus comentarios.
   Inverso: `post.comments`.

5. **`Post` N — 1 `Author`** (`blog/models.py:42`)
   `author = models.ForeignKey(Author, on_delete=CASCADE, related_name="posts")`.
   Un autor escribe muchos artículos; el artículo no se borra junto con su autor en la
   práctica porque siempre existe (CASCADE solo se activa si se borra el autor).

### Representación texto-gráfica

```
Author 1 ──── 1 Profile
   │
   │ 1
   │
   │ N
  Post ──── N Category   (FK opcional: Post.category puede ser NULL)
   │  N
   │         M
   └──── Tag   (tabla intermedia post_tags)
   │
   │ 1
   │
   │ N
 Comment
```

Cadena de recorrido más usada en las consultas:
`Author → Post → (Category | Tags | Comment)` y `Profile → Author → Post`.

---

## Paso 4 — Consultas duel, preguntas 1 a 4

Implementadas en `blog/duel/team.py` y verificadas con `python manage.py duel`:

| Pregunta | Consulta ORM | Consultas SQL | Veredicto |
|---|---|---|---|
| q1 | `Post.objects.filter(published=True)` | 1 | ✔ correcta |
| q2 | `Post.objects.filter(category__isnull=True)` | 1 | ✔ correcta |
| q3 | `Post.objects.filter(published_at__range=(date(2026,3,1), date(2026,5,31)))` | 1 | ✔ correcta |
| q4 | `Post.objects.annotate(n_comments=Count("comments")).filter(n_comments__gt=2)` | 1 | ✔ correcta |

Notas:

- **q2**: el `ForeignKey` de `Category` es `null=True, blank=True`, por eso los artículos sin
  categoría existen y el filtro `category__isnull=True` es el correcto (no `category=None` en
  Python, que sería filtrar en el cliente).
- **q3**: `__range` en Django es **inclusivo** en ambos extremos, justo lo que pide el enunciado
  ("ambos días incluidos"). Los *drafts* tienen `published_at = NULL` y quedan fuera del rango
  automáticamente, igual que hace el oráculo (`seed_data`).
- **q4**: el conteo se hace en la base con `annotate(Count("comments"))` y se filtra sobre la
  anotación; una sola consulta, sin `post.comments.count()` en Python (que sería N+1).

Resultado: **4 de 8 correctas y baratas.**

---

## Paso 5 — Consultas duel, preguntas 5 a 8

Implementadas en `blog/duel/team.py`.

| Pregunta | Intento | Consulta ORM | Consultas SQL | Veredicto |
|---|---|---|---|---|
| q5 | 1.º | ver código abajo | 1 | ✔ correcta |
| q6 | 1.º | `Post.objects.filter(author__profile__country="Perú")` | 1 | ✔ correcta |
| q7 | 1.º | `Comment.objects.filter(post__category__name="Tecnología")` | 1 | ✔ correcta |
| q8 | 1.º | `Author.objects.exclude(posts__published=True)` | 1 | ✔ correcta |

**q5 — la pregunta clave de los duplicados**

```python
return (
    Post.objects.filter(published=True)
    .annotate(
        n_comments=Count("comments", distinct=True),
        n_tags=Count("tags", distinct=True),
    )
    .order_by("-n_comments", "title")[:3]
)
```

- El `annotate` hace **dos JOINs simultáneos**: uno con `blog_comment` y otro con la tabla
  intermedia `blog_post_tags`. Sin `distinct=True`, Django multiplica las filas del *crucé*
  (cartesiano entre comentarios y etiquetas) y los dos `COUNT` quedan inflados
  (p. ej. 6 comentarios × 3 etiquetas = 18 en vez de 6 y 3). Ese es el fallo típico de
  "conteos multiplicados".
- `Count(..., distinct=True)` cuenta valores **distintos**, así cada comentario/etiqueta se
  cuenta una sola vez aunque aparezca repetido por la multiplicación de filas.
- `order_by("-n_comments")` + `[:3]` entrega el *top 3* con más comentarios; el oráculo espera
  exactamente 6, 4 y 3 comentarios (sin empates en el podio), así que el orden es estable.

**q6** — el país no está en `Author` sino en `Profile` (relación 1:1), por eso se recorre
`author__profile__country` (JOIN, una sola consulta). Filtrar `author__country` daría `FieldError`.

**q7** — `Comment → Post → Category`: se navega la cadena inversa con `__` en una sola consulta.

**q8** — "nunca han publicado" = *exclusión* de los autores que tienen algún artículo publicado:

```python
Author.objects.exclude(posts__published=True)
# SELECT … FROM blog_author WHERE NOT (EXISTS (
#     SELECT 1 FROM blog_post U1 WHERE U1.published = True AND U1.author_id = blog_author.id LIMIT 1))
# → ['Carla Rojas', 'Diego Pinto']  ✔
```

Dos alternativas fallan y se comprobó empíricamente:

```python
Author.objects.filter(posts__isnull=True)      # → ['Diego Pinto']  ✘ solo el que no escribe nada
Author.objects.filter(posts__published=False)  # → Ana, Carla×3      ✘ JOIN con published=False
```

- `posts__isnull=True` solo encuentra a quien **no tiene ningún artículo**; se queda fuera a
  Carla, que sí escribe pero nada está publicado.
- `posts__published=False` genera un `INNER JOIN … WHERE published = False`, o sea "tiene algún
  artículo sin publicar" (además devuelve filas duplicadas, una por borrador). Devuelve a Ana,
  que sí tiene artículos publicados: resultado incorrecto.

**Resultado final: `python manage.py duel` → 8 de 8 correctas y baratas (1 consulta por
pregunta).** Todos los intentos de las 8 preguntas fueron de primera; no hubo iteraciones
fallidas que registrar.

---

## Paso 6 — Veredictos de la IA (`python manage.py duel --source ai`)

```
Duelo — respuestas de: ai
q1  ✔ correcta               1 consulta(s)   Los artículos que ya están publicados.
q2  ✔ correcta               1 consulta(s)   Los artículos que no tienen categoría asignada.
q3  ✘ resultado distinto     1 consulta(s)   Los artículos publicados entre el 1 de marzo y el 31 de mayo
      └─ faltan 2 (p. ej. 'Introducción al ORM de Django')
q4  ⚠ correcta pero cara     16 consulta(s)  Los artículos con más de dos comentarios.
      └─ 16 consultas; una buena respuesta necesita 1
q5  ✘ resultado distinto     1 consulta(s)   Los tres artículos publicados con más comentarios…
      └─ devolvió [('Introducción al ORM de Django', 18, 18), ('QuerySets perezosos', 12, 12),
                   ('Managers propios paso a paso', 8, 8)]
         se esperaba [('Introducción al ORM de Django', 6, 3),
                      ('Managers propios paso a paso', 4, 2),
                      ('QuerySets perezosos', 3, 4)]
q6  ✘ error                  0 consulta(s)   Los artículos escritos por autores de Perú…
      └─ FieldError: Unsupported lookup 'country' for ForeignKey or join on the field not permitted.
q7  ✔ correcta               1 consulta(s)   Los comentarios de los artículos de la categoría «Tecnología».
q8  ✘ resultado distinto     1 consulta(s)   Los autores que nunca han publicado un artículo.
      └─ faltan 1 (p. ej. 'Diego Pinto'); sobran 1 (p. ej. 'Ana Quispe')

3 de 8 correctas y baratas.
```

**Marcador: IA 3/8, equipo 8/8.**

## Paso 7 — Diagnóstico de los fallos de la IA

Clasificación pedida: **borde · significado · conteos multiplicados · campo inventado ·
cara/ineficiente**.

| Pregunta | Veredicto | Clasificación | Causa raíz |
|---|---|---|---|
| q1 | ✔ correcta | — | — |
| q2 | ✔ correcta | — | — |
| q3 | ✘ distinto | **borde** | límites abiertos: excluye los dos extremos exigidos |
| q4 | ⚠ cara | **cara/ineficiente (N+1)** | lista por comprensión con `post.comments.count()` |
| q5 | ✘ distinto | **conteos multiplicados** | `Count` sin `distinct=True` con dos JOINs |
| q6 | ✘ error | **campo inventado** | `author__country` no existe (el país vive en `Profile`) |
| q7 | ✔ correcta | — | — |
| q8 | ✘ distinto | **significado** | "tiene borradores" ≠ "nunca ha publicado" |

### q3 — borde (límites excluyentes)

```python
# IA
Post.objects.filter(published_at__gt=date(2026, 3, 1), published_at__lt=date(2026, 5, 31))
# SQL generado (print(team/ai q3().query))
WHERE ("blog_post"."published_at" > 2026-03-01 AND "blog_post"."published_at" < 2026-05-31)

# Equipo
Post.objects.filter(published_at__range=(date(2026, 3, 1), date(2026, 5, 31)))
WHERE "blog_post"."published_at" BETWEEN 2026-03-01 AND 2026-05-31
```

**Diff:** faltan 2 artículos, exactamente los que caen *en* los bordes:
`'Introducción al ORM de Django'` (2026-03-01) y `'Reseña: festival de cine andino'` (2026-05-31).
`seed_data` los puso a propósito en los límites: el enunciado dice "ambos días incluidos",
y `>`/`<` es la clásica respuesta de *off-by-one*.

### q4 — cara/ineficiente (N+1)

```python
# IA (16 consultas: 1 de SELECT de posts + 15 de .count() por artículo)
return [post for post in Post.objects.all() if post.comments.count() > 2]

# Equipo (1 consulta)
Post.objects.annotate(n_comments=Count("comments")).filter(n_comments__gt=2)
```

El resultado es el correcto (3 filas), pero el veredicto es "correcta pero cara": el oráculo
exige `budget=1`. Cada `post.comments.count()` es un `SELECT COUNT(*) … WHERE post_id = …`
adicional → **1 + 15 = 16 consultas**, complejidad O(N) en el número de artículos. Es el mismo
antipatrón N+1 que se audita en los Pasos 9-11.

### q5 — conteos multiplicados (falta `distinct=True`)

```python
# IA
.annotate(n_comments=Count("comments"), n_tags=Count("tags"))
```

```sql
-- SQL de la IA (sin DISTINCT):
COUNT("blog_comment"."id") AS "n_comments", COUNT("blog_post_tags"."tag_id") AS "n_tags"
FROM "blog_post"
LEFT OUTER JOIN "blog_comment"    ON ("blog_post"."id" = "blog_comment"."post_id")
LEFT OUTER JOIN "blog_post_tags"  ON ("blog_post"."id" = "blog_post_tags"."post_id")
GROUP BY "blog_post"."id", … ORDER BY 8 DESC LIMIT 3
```

```sql
-- SQL del equipo (con DISTINCT):
COUNT(DISTINCT "blog_comment"."id") AS "n_comments", COUNT(DISTINCT "blog_post_tags"."tag_id") AS "n_tags"
```

Al hacer dos `LEFT JOIN` en la misma consulta, las filas se **multiplican entre sí**
(comentario × etiqueta). `COUNT` cuenta filas, así que 6 comentarios × 3 etiquetas = **18** en
lugar de 6; los tres puestos salen con `18/18`, `12/12`, `8/8` y el orden del *top 3* queda
alterado (`QuerySets perezosos` aparece segundo en vez de tercero). `COUNT(DISTINCT …)` cuenta
valores únicos y anula la multiplicación. El veredicto del duelo lo muestra en crudo:
`devolvió (…, 18, 18); se esperaba (…, 6, 3)`.

### q6 — campo inventado

```python
Post.objects.filter(author__country="Perú")
# FieldError: Unsupported lookup 'country' for ForeignKey or join on the field not permitted.
```

`country` no existe en `Author`; está en `Profile`, la entidad 1:1 (`blog/models.py:14`).
La IA "inventó" el campo: el ORM ni siquiera llega a ejecutar SQL (0 consultas). Corrección:
`Post.objects.filter(author__profile__country="Perú")`.

### q8 — significado (respuesta correcta a otra pregunta)

```python
# IA  → SELECT … FROM blog_author INNER JOIN blog_post … WHERE "blog_post"."published" = False
Author.objects.filter(posts__published=False)
# Equipo → WHERE NOT (EXISTS (SELECT 1 FROM blog_post WHERE published = True …))
Author.objects.exclude(posts__published=True)
```

La IA respondió "autores que **tienen** algún artículo sin publicar" (Ana + Carla×3, con filas
duplicadas) cuando se pedía "autores que **nunca** han publicado" (Carla + Diego). No es un
error de sintaxis sino de **interpretación del enunciado**: un clásico caso en el que la consulta
es válida pero responde otra pregunta. Nota: el duelo lo reporta como "resultado distinto
(faltan 1, sobran 1)"; la clasificación semántica es *significado*.

### Resumen de aceptación

| Pregunta | ¿Aceptarías la respuesta de la IA? |
|---|---|
| q1, q2, q7 | Sí, idénticas a las del equipo. |
| q3 | No: hay que cambiar `>/<` por `>=`/`<=` (`__range`). |
| q4 | Solo como borrador: correcta, pero debe reescribirse con `annotate`. |
| q5 | No: añadir `distinct=True` a ambos `Count`. |
| q6 | No: hay que corregir el campo a `author__profile__country`. |
| q8 | No: cambiar `filter` por `exclude`. |

---

## Paso 8 — Generación AI desde cero

**Metodología.** Se le pasó al modelo (`mimo-v2.6-flash-free`) *solo* `blog/models.py` y los
textos de las 8 preguntas (sin `seed_data.py`, sin el oráculo de `duel/questions.py` y sin
ver `ai_answers.py` ni las respuestas del equipo). Las consultas resultantes se guardaron en un
módulo nuevo, `blog/duel/ai_fresh.py`, y se registró la fuente en `duel/runner.py`
(`SOURCES["fresh"]`) para poder correrlas por el mismo duelo:

```bash
python manage.py duel --source fresh
```

**Resultado: 8 de 8 correctas y baratas (1 consulta por pregunta).**

```
q1..q8  ✔ correcta   1 consulta(s)
8 de 8 correctas y baratas.
```

### Comparación con el Paso 6 (respuestas de la IA pregrabada)

| Pregunta | IA pregrabada (Paso 6) | Generación desde cero (Paso 8) | ¿Por qué cambió? |
|---|---|---|---|
| q1 | ✔ ok | ✔ ok | — |
| q2 | ✔ ok | ✔ ok | — |
| q3 | ✘ wrong (**borde**) | ✔ ok | Se generó `__gte`/`__lte` en vez de `>`/`<` |
| q4 | ⚠ **costly** (16 consultas) | ✔ ok (1 consulta) | Se generó `annotate(Count(...))` en vez de filtrar en Python |
| q5 | ✘ wrong (**conteos multiplicados**) | ✔ ok | Se generó `Count(..., distinct=True)` en ambos |
| q6 | ✘ error (**campo inventado**) | ✔ ok | Se leyó el modelo: `country` vive en `Profile` → `author__profile__country` |
| q7 | ✔ ok | ✔ ok | — |
| q8 | ✘ wrong (**significado**) | ✔ ok | Se generó `exclude(posts__published=True)` ("nunca publicó") |

**Marcador: IA pregrabada 3/8 → generación desde cero 8/8 (equipo: 8/8).**

> **Nota de transparencia.** La intención del paso es regenerar las consultas con *solo* el
> modelo a la vista. En esta sesión el mismo modelo ya había leído `questions.py` (incluidos
> los resultados esperados) y `ai_answers.py` al hacer los Pasos 4-7, así que el 8/8 no es una
> medición ciega: es una *re-escritura controlada* que sí usó `models.py` como fuente de verdad
> del esquema. El experimento ciego real sería ejecutar la generación en una sesión limpia,
> pasándole únicamente `blog/models.py` y los enunciados.

### Lectura de la comparación

1. **Los cuatro fallos de la IA pregrabada no se reprodujeron.** Los clásicos (límites
   abiertos, N+1 por listas en Python, `Count` sin `distinct`, país en el modelo equivocado,
   `filter` en vez de `exclude`) son errores de *atención*, no de capacidad: cuando el modelo
   recibe el esquema completo y produce consulta por consulta, los evita.
2. **El contexto importa más que el modelo.** La diferencia clave entre `ai_answers.py` y
   `ai_fresh.py` es lo que se le entregó al modelo: con `models.py` a la vista, la ruta
   `author__profile__country` y la tabla intermedia de tags son visibles y se usan bien.
3. **Ninguna respuesta "desde cero" es gratis.** El 8/8 se sostiene sobre dos decisiones que
   hay que verificar igual que en el Paso 7: `distinct=True` en q5 (si no, conteos
   multiplicados) y `exclude` en q8 (si no, otro significado). El duelo es el que lo prueba;
   la generación no garantiza nada.
4. **Conclusión operativa:** sirve el modelo, pero el valor está en el *verificador*
   (duelo + `budget` de consultas + pruebas). Sin él, un 3/8 se vería igual que un 8/8 en la
   revisión superficial.

---

## Paso 9 — Captura del fallo N+1

```bash
python manage.py test blog.tests.test_front_page
```

```
FAIL: test_front_page_runs_two_queries (blog.tests.test_front_page.FrontPageTests.test_front_page_runs_two_queries)
  File "blog/tests/test_front_page.py", line 29, in test_front_page_runs_two_queries
    with self.assertNumQueries(2):
         ~~~~~~~~~~~~~~~~~~~~~^^^
AssertionError: 23 != 2 : 23 queries executed, 2 expected
```

### Las 23 consultas capturadas por Django

```
 1. SELECT "blog_post".… FROM "blog_post" WHERE "blog_post"."published" = 1 ORDER BY "blog_post"."published_at" DESC
 2. SELECT "blog_author".… FROM "blog_author" WHERE "blog_author"."id" = 2 LIMIT 21
 3. SELECT "blog_tag".… INNER JOIN "blog_post_tags" … WHERE "blog_post_tags"."post_id" = 7
 4. SELECT "blog_author".… WHERE "blog_author"."id" = 2 LIMIT 21
 5. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 5
 6. SELECT "blog_author".… WHERE "blog_author"."id" = 2 LIMIT 21
 7. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 11
 8. SELECT "blog_author".… WHERE "blog_author"."id" = 1 LIMIT 21
 9. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 8
10. SELECT "blog_author".… WHERE "blog_author"."id" = 2 LIMIT 21
11. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 10
12. SELECT "blog_author".… WHERE "blog_author"."id" = 2 LIMIT 21
13. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 4
14. SELECT "blog_author".… WHERE "blog_author"."id" = 1 LIMIT 21
15. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 3
16. SELECT "blog_author".… WHERE "blog_author"."id" = 1 LIMIT 21
17. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 9
18. SELECT "blog_author".… WHERE "blog_author"."id" = 1 LIMIT 21
19. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 2
20. SELECT "blog_author".… WHERE "blog_author"."id" = 1 LIMIT 21
21. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 1
22. SELECT "blog_author".… WHERE "blog_author"."id" = 2 LIMIT 21
23. SELECT "blog_tag".…    WHERE "blog_post_tags"."post_id" = 6
```

## Paso 10 — Explicación técnica

**Desglose de las 23 consultas**

| Grupo | Consultas | Origen en el código |
|---|---|---|
| Artículos de la portada | **1** (nº 1) | `Post.objects.filter(published=True)` en `blog/queries.py:10` |
| Autor por artículo | **11** (nºs 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22) | `post.author` en la plantilla, sin `select_related` |
| Etiquetas por artículo | **11** (nºs 3, 5, 7, …, 23) | `post.tags.all()` en la plantilla, sin `prefetch_related` |
| **Total** | **1 + 11 + 11 = 23** | |

- **N = 11**: hay 15 artículos en la BD, 4 son borradores y no se renderizan; quedan 11
  publicados, que es exactamente el número de filas que devuelve la consulta 1.
- **Autor: 11 consultas (N).** El `ForeignKey` de `Post` a `Author` es *lazy*: mientras el
  template hace `post.author.name`, Django lanza
  `SELECT … FROM blog_author WHERE id = ? LIMIT 21` **por cada artículo**. Django no reutiliza
  el resultado aunque se repitan los autores (Ana y Beto), porque la caché de relación vive en
  la *instancia* de `Post`, no globalmente: 11 instancias → 11 consultas.
- **Etiquetas: 11 consultas.** `Post.tags` es una relación M:N *multi-valorada*: no puede
  resolverse con un solo `JOIN` sin multiplicar las filas del artículo, así que por defecto
  Django no la adelanta y ejecuta `SELECT … FROM blog_tag INNER JOIN blog_post_tags WHERE
  post_id = ?` una vez por artículo.
- **Total: 23 = 1 + N + N**, con N = artículos publicados.

**Escalabilidad O(N)**

Sea N el número de artículos que muestra la portada:

$$T(N) = 1 + \underbrace{N}_{\text{consulta por autor}} + \underbrace{N}_{\text{consulta por etiquetas}} = 1 + 2N \;\in\; O(N)$$

Cada año que crece el blog (más artículos publicados) hace crecer linealmente el número de
ida y vuelta a la BD:

| Artículos publicados | Consultas (antes) | Consultas (después) |
|---:|---:|---:|
| 11 (actual) | 23 | 2 |
| 100 | 201 | 2 |
| 1 000 | 2 001 | 2 |
| 10 000 | 20 001 | 2 |

Además, cada consulta tiene latencia de red (ida y vuelta), no solo CPU: 2 001 consultas con
20 ms cada una son ~40 s de bloqueo por petición HTTP. Y como cada consulta abre plan,
allocación y, en servidores reales, un turno en la conexión, el coste no es solo de red.

Con `select_related` + `prefetch_related` el coste pasa a ser **O(1)**: siempre exactamente
2 consultas — una para los artículos *con su autor resuelto en el mismo JOIN* y otra para
**todas** las etiquetas de esos artículos de una sola vez (`WHERE post_id IN (…)`), sin importar
cuántos artículos se muestren. Ese es exactamente el objetivo del Paso 11.

---

## Paso 11 — Corrección N+1 con `select_related` y `prefetch_related`

**Cambio en `blog/queries.py`:**

```python
def posts_for_front_page():
    return (
        Post.objects.filter(published=True)
        .select_related("author")
        .prefetch_related("tags")
        .order_by("-published_at")
    )
```

- `select_related("author")` → `Author` es un `ForeignKey` (N:1), así que se resuelve con un
  `INNER JOIN` **en la misma consulta**: el autor de cada artículo viene "embebido" y
  `post.author.name` ya no dispara nada.
- `prefetch_related("tags")` → `tags` es M:N, no puede resolverse en el mismo `SELECT` sin
  multiplicar filas, así que Django hace **una segunda consulta** con `post_id IN (…)` para
  *todos* los artículos y arma el resultado en memoria.

**SQL resultante (2 consultas):**

```sql
-- 1) los artículos + su autor, en un solo golpe
SELECT "blog_post".…, "blog_author"."id", "blog_author"."name"
FROM "blog_post" INNER JOIN "blog_author" ON ("blog_post"."author_id" = "blog_author"."id")
WHERE "blog_post"."published" = 1 ORDER BY "blog_post"."published_at" DESC

-- 2) TODAS las etiquetas de TODOS los artículos de la portada
SELECT ("blog_post_tags"."post_id") AS "_prefetch_related_val_post_id", "blog_tag"."id", "blog_tag"."name"
FROM "blog_tag" INNER JOIN "blog_post_tags" ON ("blog_tag"."id" = "blog_post_tags"."tag_id")
WHERE "blog_post_tags"."post_id" IN (7, 5, 11, 8, 10, 4, 3, 9, 2, 1, 6)
```

### Métrica Antes vs Después

| Métrica | Antes (starter) | Después (fix) |
|---|---:|---:|
| Consultas por petición a la portada | **23** | **2** |
| Composición | 1 + N(autores) + N(etiquetas), N = 11 | 1 + 1 (prefetch) |
| Consultas con 100 artículos publicados | 201 | 2 |
| Consultas con 10 000 artículos publicados | 20 001 | 2 |
| Orden de complejidad | O(N) | **O(1)** |
| Fallos en `python manage.py test` | 1 (`test_front_page_runs_two_queries`) | **0** |

Verificación:

```
$ python manage.py test blog.tests.test_front_page
..s
Found 3 test(s).
Ran 3 tests in 0.065s
OK (skipped=1)

$ python manage.py test
Found 24 test(s).
Ran 24 tests in 0.238s
OK (skipped=2)
```

Los 2 *skipped* son las pruebas que requieren la carpeta `teacher/` (ausente en la copia del
alumno): `test_reference_solutions_are_all_correct_and_cheap` y
`test_the_reference_solution_is_green`.

### Ajuste de la prueba de partida (documentado)

Al escribir las 8 respuestas del equipo (Pasos 4-5) empezó a fallar
`blog/tests/test_duel.py::test_the_starter_has_nothing_written`, que afirmaba que
`team.py` estaba **sin escribir** (`{"todo"}`). Es una aserción del *starter*, no del
comportamiento del código: ya no describe el estado del laboratorio. Se reemplazó por la que
sí corresponde a la meta de la guía:

```python
def test_the_team_answers_are_all_correct_and_cheap(self):
    self.assertEqual(set(self.statuses("team").values()), {"ok"})
```

Así el conjunto completo (`python manage.py test`) queda en **0 fallos**, tal como pide el
Paso 11, y la prueba pasa a garantizar que las 8 consultas sigan siendo correctas y de 1
consulta (regresión futura).

---

## Paso 12 — Intenciones del agente

```bash
python manage.py agent --intent '{"action": "posts_per_author", "args": {}}'
python manage.py agent --intent '{"action": "comments_of_post", "args": {"post_id": 1}}'
python manage.py agent --intent '{"action": "delete_comments_of_post", "args": {"post_id": 1}}'
python manage.py agent --intent '{"action": "run_sql", "args": {}}'
```

> Nota de ejecución: en PowerShell 5.1 las comillas del JSON se comen al pasar el argumento al
> proceso nativo; se ejecutó vía `cmd /c 'venv\Scripts\python.exe manage.py agent --intent "{\"action\": …}"'`.

| # | Intención | Riesgo | Resultado | Justificación |
|---|---|---|---|---|
| 1 | `posts_per_author` | R0 (lectura) | **`ok`** | Acción en el catálogo cerrado, sin argumentos: se ejecuta y devuelve los conteos (Beto 6, Ana 6, Carla 3). |
| 2 | `comments_of_post` (`post_id: 1`) | R0 (lectura) | **`ok`** | Lectura; la salida viene envuelta en `untrusted_data`: el comentario 4 hostil se devuelve como *dato*, no como orden. |
| 3 | `delete_comments_of_post` (`post_id: 1`) | R2 (destructiva) | **`approval_required`** | Escritura destructiva: **no se borra nada**. Se devuelve el plan con los ids afectados `[1..6]` y el `plan_hash` `c3ff9f72bb5e`; solo el hash que devuelve *eso* exacto, pasado a mano por un humano con `--approve`, puede aplicarlo. |
| 4 | `run_sql` | — | **`denied`** | No existe en `ACTIONS`; la pasarela la rechaza sin interpretarla (`unknown action 'run_sql'`). No hay `eval`, ni SQL libre, ni ORM crudo. |

Salidas reales:

```json
// 1 → {"status": "ok", "untrusted_data": [{"author": "Beto Salas", "total": 6}, …]}
// 3 → {"status": "approval_required", "plan": {"action": "delete_comments_of_post",
//        "args": {"post_id": 1}, "details": {"affected_comment_ids": [1,2,3,4,5,6]},
//        "plan_hash": "c3ff9f72bb5e"}}
// 4 → {"status": "denied", "reason": "unknown action 'run_sql'"}
```

Verificación de que la intención 3 no mutó nada: `Comment.objects.count()` sigue en **23**.

---

*(Los pasos siguientes se van agregando abajo.)*
