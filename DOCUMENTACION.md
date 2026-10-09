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

*(Los pasos siguientes se van agregando abajo.)*
