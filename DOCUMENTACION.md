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

*(Los pasos siguientes se van agregando abajo.)*
