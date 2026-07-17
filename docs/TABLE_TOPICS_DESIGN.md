# Detailed Design: Table Topics & Collections

This document specifies the design details for the Table Topics (Reflections) and custom Collections (Bookmarking) subsystem.

---

## 1. UI/UX Design & Layout Details

To match the look and feel of the platform (especially the Issue Tracker and Journals), Table Topics will use a **dual-pane layout** (`topics-layout`) with a navigation sidebar on the left and the main interactive content pane on the right.

### Page Shell: Dual-Pane Layout
* **Sidebar (`.topics-sidebar`)**:
  * Pinned navigation items with icons:
    * `Featured Topic` (icon: `fa-star`, highlights today's prompt).
    * `Explore Feed` (icon: `fa-globe`, global public/club stream).
    * `My Journal` (icon: `fa-book-open`, chronological list of own essays).
  * **Collections Section**:
    * Dynamic list of custom user collections (icon: `fa-folder`, e.g., "Speech Ideas").
    * A ghost button: `+ Create Collection` which triggers a simple inline creation input or modal.
  * **Admin Section** (visible to `sysadmin` only):
    * `Manage Topics` (icon: `fa-tasks`, drafts and publishing pipeline).
* **Main Pane (`.topics-main`)**:
  * Displays the selected view. Uses smooth transitions (opacity fade-in) when changing tabs.

---

### Detailed Views & Page Layouts

#### A. Featured Topic View
1. **Prompt Header**: Prominent card styled with a light pink background (`#faf0f1`), a left maroon border (`border-left: 4px solid #772432`), and a title.
2. **Essay Composing Card**:
   * Textarea with placeholder text, styled with a modern focus state.
   * Word counter dynamically showing `Word Count: X words` below the textbox.
   * Radio group selector for visibility options (`Private`, `Club Members`, `Public`).
   * Buttons: `Save Reflection` (maroon pill button) and `Delete` (outline button, if editing).
3. **Response Display Card**:
   * If the user already submitted a reflection, their essay is rendered from Markdown into HTML with formatting. An `Edit` button toggles back to the editor.
4. **Community reflections grid**:
   * Under the user's reflection, displays essays written by others on this exact prompt, formatted as snippet cards.

#### B. Explore Feed View
* Grid or list of response cards. Each card displays:
  * **Header**: Topic title, author's avatar, name, and their active club context badge (e.g. "Shanghai Leadership").
  * **Content**: First 300 characters of the essay, fading out with a read-more link.
  * **Footer**: Date, comment count, and a bookmark/favorite icon button.

#### C. My Journal View
* Vertical chronological timeline of all reflections written by the current user. 
* Displays visibility status badges (`Private`, `Club`, `Public`) and edit/delete triggers.

#### D. Collection Detail View
* Pinned header showing the collection name (e.g. "Speech Material").
* Split list of items in this collection:
  * **Topics**: A list of saved prompt questions with links to write a response.
  * **Reflections**: Essays saved by the user with their authors and links to read full threads.

#### E. Bookmark Dropdown (Adding to Collections)
* Clicking the bookmark icon on any card/detail page opens a floating dropdown (`z-index: var(--z-popover)`).
* Displays a list of the user's collections with checkbox toggles. Checking a checkbox adds the item, unchecking removes it via an AJAX request.
* A small inline text field: `Create & Add` at the bottom of the dropdown enables instant folder creation.

---

## 2. Database Models & Schema

We will add a new model file `app/models/topic.py` with the following schemas:

### Core Tables

#### `Topic`
* `id`: PK (`db.Integer`)
* `title`: `db.String(255)`, `nullable=False`
* `body`: `db.Text`, `nullable=False`
* `status`: `db.String(20)`, `default='draft'`, `nullable=False`
* `published_at`: `db.DateTime`, `nullable=True`
* `created_by_id`: `db.Integer` (FK to `users.id`, `nullable=True`, `ondelete='SET NULL'`)
* `created_at`: `db.DateTime`, `default=utc`
* `updated_at`: `db.DateTime`, `default=utc`, `onupdate=utc`

#### `TopicResponse` (the essay reflection)
* `id`: PK (`db.Integer`)
* `topic_id`: `db.Integer` (FK to `topics.id`, `nullable=True`, `ondelete='SET NULL'`, `index=True`)
* `author_id`: `db.Integer` (FK to `users.id`, `nullable=False`, `ondelete='CASCADE'`, `index=True`)
* `club_id`: `db.Integer` (FK to `clubs.id`, `nullable=True`, `ondelete='SET NULL'`, `index=True`) — display only
* `title`: `db.String(255)`, `nullable=True`
* `body`: `db.Text`, `nullable=False`
* `visibility`: `db.String(20)`, `default='private'`, `nullable=False` (options: `'private'`, `'club'`, `'public'`)
* `created_at`: `db.DateTime`, `default=utc`
* `updated_at`: `db.DateTime`, `default=utc`, `onupdate=utc`

#### `TopicComment` (1-level nested comments)
* `id`: PK (`db.Integer`)
* `response_id`: `db.Integer` (FK to `topic_responses.id`, `nullable=False`, `ondelete='CASCADE'`, `index=True`)
* `author_id`: `db.Integer` (FK to `users.id`, `nullable=False`, `ondelete='CASCADE'`, `index=True`)
* `parent_id`: `db.Integer` (FK to `topic_comments.id`, `nullable=True`, `ondelete='CASCADE'`, `index=True`) — null for top-level, non-null for reply
* `body`: `db.Text`, `nullable=False`
* `created_at`: `db.DateTime`, `default=utc`
* `updated_at`: `db.DateTime`, `default=utc`, `onupdate=utc`

### Collection Tables

#### `TopicCollection` (private collections list)
* `id`: PK (`db.Integer`)
* `user_id`: `db.Integer` (FK to `users.id`, `nullable=False`, `ondelete='CASCADE'`, `index=True`)
* `name`: `db.String(100)`, `nullable=False`
* `created_at`: `db.DateTime`, `default=utc`

#### `CollectionItem` (junction table for saved items)
* `id`: PK (`db.Integer`)
* `collection_id`: `db.Integer` (FK to `topic_collections.id`, `nullable=False`, `ondelete='CASCADE'`, `index=True`)
* `topic_id`: `db.Integer` (FK to `topics.id`, `nullable=True`, `ondelete='CASCADE'`, `index=True`)
* `response_id`: `db.Integer` (FK to `topic_responses.id`, `nullable=True`, `ondelete='CASCADE'`, `index=True`)
* `created_at`: `db.DateTime`, `default=utc`

*Unique constraints will ensure a topic or response is only added to a specific collection once.*

---

## 3. Web Service Layer (`app/services/topics_service.py`)

Handles atomic operations:
* **Topic CRUD**: `create_topic`, `publish_topic`, `update_topic`, `delete_topic`.
* **Response CRUD**: `create_response`, `update_response`, `delete_response`.
* **Comment CRUD**: `add_comment`, `update_comment`, `delete_comment`.
* **Collection CRUD**:
  * `create_collection(user_id, name)`
  * `delete_collection(collection_id, user_id)`
  * `add_item_to_collection(collection_id, topic_id=None, response_id=None)`
  * `remove_item_from_collection(collection_id, topic_id=None, response_id=None)`
  * `get_user_collections_for_item(user_id, topic_id=None, response_id=None)` (returns a list of collection IDs this item currently belongs to).

---

## 4. Routes Blueprint & Views

Registered blueprint `topics_bp`:
* **`GET /topics`**: Dashboard. Shows the main layout, sidebar navigation, featured topic, and recent activities.
* **`GET /topics/explore`**: Explore feed view.
* **`GET /topics/mine`**: User's own journal timeline.
* **`GET /topics/collection/<int:collection_id>`**: Detail view of a single collection.
* **`POST /topics/collections/create`**: Create a custom named collection.
* **`POST /topics/collections/add-item`**: Toggle item inside user collections (AJAX, JSON endpoint).
* **`GET /topic/<int:topic_id>`**: Individual topic detail.
* **`POST /topic/<int:topic_id>/respond`**: Essay submission endpoint.
* **`GET /response/<int:response_id>`**: Essay details + comments stream.
* **`POST /response/<int:response_id>/comment`**: Add/edit comment.
* **`POST /comment/<int:comment_id>/delete`**: Delete comment.
* **`GET /topics/admin`**: sysadmin-only panel.
