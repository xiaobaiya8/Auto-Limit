# Auto-Limit 国际化 (i18n) 指南

## 概述

Auto-Limit 项目使用 `Flask-Babel` 实现了国际化(i18n)，以支持多语言界面和日志。

- **支持的语言**:
  - `zh`: 中文 (默认)
  - `en`: 英文
- **核心机制**:
  - **自动检测**: 根据浏览器 `Accept-Language` 头自动选择语言。
  - **手动切换**: 用户可在界面右上角手动切换语言。
  - **持久化**: 用户的语言选择会保存在 `app/data/config.json` 中，确保后台任务（如日志记录）也能使用正确的语言。

---

## 开发与翻译工作流

当你在开发过程中添加了新的文本或者修改了现有文本，请遵循以下三步流程来更新翻译：

### 第一步：在代码中标记待翻译文本

所有需要被翻译的用户可见文本，都必须使用 `_()` 函数包裹起来。

- **Python 代码中**:
  ```python
  from flask_babel import gettext as _
  
  # 示例
  log_manager.log_event("CONFIG", _("配置已更新"))
  flash(_("操作成功！"))
  ```

- **HTML 模板中 (Jinja2)**:
  ```html
  <h1>{{ _('系统状态') }}</h1>
  <button>{{ _('保存') }}</button>
  <p>{{ _('当前有 %(num)s 个活跃连接', num=active_connections) }}</p>
  ```

### 第二步：提取文本并更新翻译文件

完成代码修改后，需要扫描整个项目，将所有被 `_()` 包裹的新文本或修改过的文本提取出来，并更新到翻译源文件 (`.po` 文件)中。

1. **打开终端**，进入项目根目录。

2. **运行 `pybabel extract` 命令**：
   这个命令会扫描项目，并根据 `babel.cfg` 的配置，生成一个翻译模板文件 `messages.pot`。
   ```bash
   pybabel extract -F babel.cfg -o messages.pot .
   ```

3. **运行 `pybabel update` 命令**：
   这个命令会将 `messages.pot` 中的新内容合并到各个语言的 `.po` 文件中。
   ```bash
   pybabel update -i messages.pot -d app/translations
   ```
   
   现在，你可以打开 `app/translations/zh/LC_MESSAGES/messages.po` 和 `app/translations/en/LC_MESSAGES/messages.po` 文件，会看到新的待翻译条目已经加进去了。找到 `msgstr "" ` 的行，在双引号中填入对应的翻译即可。

### 第三步：编译翻译并测试

翻译完成后，需要将 `.po` 文件编译成二进制的 `.mo` 文件，这样应用才能读取它们。

1. **运行 `pybabel compile` 命令**：
   ```bash
   pybabel compile -d app/translations
   ```
   这个命令会为每个语言目录生成或更新 `.mo` 文件。

2. **重启应用并测试**：
   现在重启 Docker 容器或 Python 应用，访问界面并切换语言，你应该能看到新的翻译已经生效了。

---

## 文件结构简介

- `babel.cfg`: `pybabel` 的配置文件，定义了要扫描哪些文件。
- `messages.pot`: 翻译模板文件，是所有待翻译文本的集合。
- `app/translations/`: 所有语言翻译文件的存放目录。
  - `<lang>/LC_MESSAGES/messages.po`: 某个语言的翻译源文件（纯文本，可编辑）。
  - `<lang>/LC_MESSAGES/messages.mo`: 编译后的二进制文件，应用实际读取的文件。

---

## 常见问题

- **翻译不生效?**
  - **忘记编译**: 最常见的原因。请务必执行 `pybabel compile`。
  - **缓存问题**: 清除浏览器缓存，或强制刷新页面 (`Ctrl+F5`)。
  - **代码未重启**: 如果是修改了 Python 代码中的文本，需要重启应用。

- **`pybabel` 命令未找到?**
  - 请确保你已经通过 `pip install -r requirements.txt` 安装了 `Babel` 依赖。

- **日志翻译不正确?**
  - 后台任务的翻译依赖于 `app/data/config.json` 中的语言设置。请确保在切换语言后，该文件中的 `language` 字段已正确更新。

## 功能特性

- **自动语言检测** - 根据浏览器语言自动选择界面语言
- **手动语言切换** - 用户可以在界面上手动切换语言
- **独立翻译文件** - 每种语言都有独立的翻译文件
- **实时切换** - 无需重启应用即可切换语言

## 使用方法

### 用户使用

1. **自动检测**：打开应用时会根据浏览器语言自动选择界面语言
2. **手动切换**：点击导航栏的"语言"下拉菜单选择所需语言
3. **语言保持**：选择的语言会保存在会话中，直到浏览器关闭

### 开发者使用

#### 1. 翻译管理

使用 `manage_translations.py` 脚本管理翻译：

```bash
# 提取新的翻译字符串
python manage_translations.py extract

# 更新现有翻译文件
python manage_translations.py update

# 编译翻译文件
python manage_translations.py compile

# 执行完整流程
python manage_translations.py all

# 添加新语言 (例如法语)
python manage_translations.py init fr
```

#### 2. 在模板中添加翻译

在 HTML 模板中使用 `_()` 函数标记需要翻译的文本：

```html
<!-- 简单文本 -->
<h1>{{ _('系统状态') }}</h1>

<!-- 带变量的文本 -->
<span>{{ _('%(count)d 个已启用', count=enabled_count) }}</span>

<!-- JavaScript 中的翻译 -->
<script>
const message = '{{ _("加载中...") }}';
</script>
```

#### 3. 在 Python 代码中添加翻译

```python
from flask_babel import _

# 在视图函数中
@app.route('/')
def index():
    message = _('欢迎使用 Auto-Limit')
    return render_template('index.html', message=message)

# 在日志中
log_manager.log_event("INFO", _("系统启动成功"))
```

## 文件结构

```
app/
├── translations/           # 翻译文件目录
│   ├── zh/                # 中文翻译
│   │   └── LC_MESSAGES/
│   │       ├── messages.po # 翻译源文件
│   │       └── messages.mo # 编译后的翻译文件
│   └── en/                # 英文翻译
│       └── LC_MESSAGES/
│           ├── messages.po
│           └── messages.mo
├── templates/             # 模板文件
│   ├── base.html         # 基础模板 (包含语言切换)
│   ├── index.html        # 首页模板
│   └── ...
babel.cfg                  # Babel 配置文件
messages.pot              # 翻译模板文件
manage_translations.py    # 翻译管理脚本
```

## 添加新语言

1. **初始化新语言**：
   ```bash
   python manage_translations.py init <语言代码>
   ```

2. **更新应用配置**：
   在 `app/__init__.py` 中添加新语言到 `LANGUAGES` 列表：
   ```python
   LANGUAGES=['zh', 'en', 'fr']  # 添加法语
   ```

3. **更新语言菜单**：
   在 `app/templates/base.html` 中添加新语言选项：
   ```html
   <li><a class="dropdown-item" href="{{ url_for('main.set_language', language='fr') }}">Français</a></li>
   ```

4. **翻译文本**：
   编辑 `app/translations/<语言代码>/LC_MESSAGES/messages.po` 文件，填写翻译内容

5. **编译翻译**：
   ```bash
   python manage_translations.py compile
   ```

## 翻译工作流程

1. **开发新功能** → 在代码中使用 `_()` 标记需要翻译的文本
2. **提取字符串** → 运行 `python manage_translations.py extract`
3. **更新翻译文件** → 运行 `python manage_translations.py update`
4. **翻译文本** → 编辑 `.po` 文件填写翻译
5. **编译翻译** → 运行 `python manage_translations.py compile`
6. **测试** → 重启应用并测试各语言界面

## 注意事项

- 修改翻译文件后需要重新编译才能生效
- 添加新的翻译字符串后需要重启应用
- 语言选择保存在用户会话中，浏览器关闭后会重置
- 建议定期运行 `python manage_translations.py all` 保持翻译文件同步

## 故障排除

### 翻译不生效
1. 确保翻译文件已编译：`python manage_translations.py compile`
2. 检查翻译文件格式是否正确
3. 重启应用

### 新语言不显示
1. 确保语言代码已添加到 `LANGUAGES` 配置中
2. 检查翻译文件是否存在并已编译
3. 确保语言菜单中有对应选项

### 字符串未翻译
1. 确保使用了 `_()` 函数标记
2. 运行 `python manage_translations.py extract` 提取新字符串
3. 在 `.po` 文件中填写翻译内容
4. 重新编译翻译文件 