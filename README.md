<!-- 顶部标题 & 统计徽章 -->
<div align="center">
  <h1 style="margin-top: 0" align="center">Python API for JMComic</h1>

  <p align="center">
    <strong>简体中文</strong> •
    <a href="./assets/readme/README-en.md">English</a> •
    <a href="./assets/readme/README-jp.md">日本語</a> •
    <a href="./assets/readme/README-kr.md">한국어</a>
  </p>

  <p align="center">
  <strong>提供 Python API 访问禁漫天堂（网页端 & 移动端），集成 GitHub Actions 下载器🚀</strong>
  </p>

[![GitHub](https://img.shields.io/badge/-GitHub-181717?logo=github)](https://github.com/hect0x7)
[![Stars](https://img.shields.io/github/stars/hect0x7/JMComic-Crawler-Python?color=orange&label=stars&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/stargazers)
[![Forks](https://img.shields.io/github/forks/hect0x7/JMComic-Crawler-Python?color=green&label=forks&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/forks)
[![GitHub latest releases](https://img.shields.io/github/v/release/hect0x7/JMComic-Crawler-Python?color=blue&label=version)](https://github.com/hect0x7/JMComic-Crawler-Python/releases/latest)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/jmcomic?style=flat&color=hotpink)](https://pepy.tech/projects/jmcomic)
[![Licence](https://img.shields.io/github/license/hect0x7/JMComic-Crawler-Python?color=red)](https://github.com/hect0x7/JMComic-Crawler-Python)

</div>


> 本项目封装了一套可用于爬取JM的Python API.
> 
> 你可以通过简单的几行Python代码，实现下载JM上的本子到本地，并且是处理好的图片。
> 
> **🧭 快速指路**
> - [教程：使用 GitHub Actions 下载禁漫本子](./assets/docs/sources/tutorial/1_github_actions.md)
> - [教程：导出并下载你的禁漫收藏夹数据](./assets/docs/sources/tutorial/10_export_favorites.md)
> - [教程：下载后转为 PDF / ZIP / 长图](./assets/docs/sources/tutorial/13_export_and_feature.md)
> - [塔台广播：欢迎各位机长加入并贡献代码](./.github/CONTRIBUTING.md)
> 
> **友情提示：珍爱JM，为了减轻JM的服务器压力，请不要一次性爬取太多本子，西门🙏🙏🙏**.
> 


![introduction.jpg](https://raw.githubusercontent.com/hect0x7/hect0x7/master/images/jmcomic-intro-main.png)


## 项目介绍

本项目的核心功能是下载本子。

基于此，设计了一套方便使用、便于扩展，能满足一些特殊下载需求的框架。

目前核心功能实现较为稳定，项目也处于维护阶段。

除了下载功能以外，也实现了其他的一些禁漫接口，按需实现。目前已有功能：

- 登录
- 搜索本子（支持所有搜索项）
- 图片下载解码
- 分类/排行榜
- 本子/章节详情
- 个人收藏夹
- 接口加解密（APP的接口）

## 安装教程

> ⚠如果你没有安装过 Python，需要先前往 [Python 官网下载](https://www.python.org/downloads/) 再执行以下步骤。
>**推荐使用 Python 3.12及以上版本**

* 通过pip官方源安装（推荐，并且更新也是这个命令）

  ```shell
  pip install jmcomic -U
  ```
* 通过源代码安装

  ```shell
  pip install git+https://github.com/hect0x7/JMComic-Crawler-Python
  ```

## 部署

### Docker 部署 HTTP 服务

本仓库提供了一个 Docker 服务封装，可以把 `jmcomic` 暴露为 HTTP API，方便 AstrBot 或其他 Docker 服务在内网中调用。建议只部署在可信的 Docker 内网中。

1. 复制环境变量模板：

   ```sh
   cp .env.example .env
   ```

   Windows PowerShell 可使用：

   ```powershell
   Copy-Item .env.example .env
   ```

2. 按需修改 `.env`。不填写 `JM_USERNAME` 和 `JM_PASSWORD` 时，会以未登录模式运行，基本查询和下载功能仍可使用。需要代理时可以填写 `JM_PROXY`，例如：

   ```env
   JM_PROXY=http://host.docker.internal:7890
   ```

3. 构建并启动：

   ```sh
   docker compose up -d --build
   ```

4. 检查服务状态：

   ```sh
   curl http://localhost:8000/health
   ```

5. 提交下载任务：

   ```sh
   curl -X POST http://localhost:8000/tasks \
     -H "Content-Type: application/json" \
     -d "{\"album_ids\":[\"123\"],\"photo_ids\":[],\"output_format\":\"pdf\"}"
   ```

   默认输出格式为 `pdf`。如果只生成一个 PDF，下载接口会直接返回 PDF 文件；如果一次任务生成多个 PDF，则返回包含这些 PDF 的 zip 包。如果希望保留原始图片目录结构，可以把 `output_format` 设置为 `zip`、`raw` 或 `original`。

6. 查看任务状态并下载结果：

   ```sh
   curl http://localhost:8000/tasks/<task_id>
   curl -L http://localhost:8000/tasks/<task_id>/archive -o jmcomic.pdf
   ```

更多接口示例见 [Docker 服务文档](./docs/docker-service.md)。

### Docker 环境变量配置

常用配置都可以通过 `.env` 暴露给 Docker 服务：

- `JM_SERVICE_PORT`：宿主机暴露端口，默认 `8000`。
- `JM_DOWNLOAD_DIR`：容器内下载目录，默认 `/data/downloads`。
- `JM_PROXY`：HTTP/HTTPS 代理地址，留空则不使用代理。
- `JM_USERNAME` / `JM_PASSWORD`：禁漫账号密码，两者都填写时启用登录；都留空时不登录。
- `JM_CLIENT_IMPL`：客户端实现，常用 `api` 或 `html`。
- `JM_CLIENT_RETRY_TIMES`：请求重试次数。
- `JM_REQUEST_TIMEOUT`：请求超时时间。
- `JM_IMAGE_THREADS`：图片并发下载数量。
- `JM_PHOTO_THREADS`：章节并发下载数量。
- `JM_IMAGE_SUFFIX`：图片转换后缀，例如 `.jpg` 或 `.png`，留空则保持默认。
- `JM_DIR_RULE`：下载目录规则。
- `JM_DEFAULT_OUTPUT_FORMAT`：默认输出格式，支持 `pdf`、`zip`、`raw`、`original`。

完整说明见 [.env.example](./.env.example)。

### 导入 AstrBot Skill

本仓库内置 AstrBot Skill：

```text
astrbot/skills/jmcomic-downloader
```

导入方式：

1. 将 `astrbot/skills/jmcomic-downloader` 目录打包成 zip：

   ```sh
   cd astrbot/skills
   zip -r jmcomic-downloader.zip jmcomic-downloader
   ```

2. 在 AstrBot WebUI 中进入 `Plugins` -> `Skills`，上传 `jmcomic-downloader.zip`。

3. 在 AstrBot 容器中配置服务地址：

   ```env
   JMCOMIC_SERVICE_URL=http://jmcomic-service:8000
   ```

4. 用户可以用类似以下内容触发：

   ```text
   下载 JM 123
   下载 JM 章节 p456
   ```

Skill 会将 `jmcomic`、`jm`、`禁漫`、`jm天堂`、`禁漫天堂` 相关的查询和下载请求识别为本服务相关任务。更多说明见 [AstrBot Skill 文档](./docs/astrbot-skill.md)。

### Docker 网络注意事项

从宿主机测试服务时，可以访问：

```text
http://localhost:8000
```

但从 AstrBot 容器内部访问时，不能使用 `localhost`，因为它指向 AstrBot 容器自己。AstrBot 应访问：

```text
http://jmcomic-service:8000
```

这个地址只有在 AstrBot 和 `jmcomic-service` 位于同一个用户自定义 Docker bridge 网络时才可解析。Docker 默认的 `bridge` 网络不提供这种容器名 DNS 解析；Docker Compose 默认创建的是用户自定义 bridge 网络，同一个 compose 文件里的服务可以直接用服务名互访。

如果 AstrBot 和本服务属于不同的 compose 项目，建议创建共享网络：

```sh
docker network create astrbot-net
```

然后在两个 compose 文件中都声明：

```yaml
networks:
  astrbot-net:
    external: true
```

并把 AstrBot 服务和 `jmcomic-service` 都加入 `astrbot-net`。如果服务名不是 `jmcomic-service`，请调整 `JMCOMIC_SERVICE_URL`，或给该服务配置 network alias。

## 快速上手

### 1. 下载本子方法

只需要使用如下代码，就可以下载本子`JM123`的所有章节的图片：

```python
import jmcomic  # 导入此模块，需要先安装.
jmcomic.download_album('123')  # 传入要下载的album的id，即可下载整个album到本地.

# 也可以使用 Async API (详见教程: https://jmcomic.readthedocs.io/zh-cn/latest/tutorial/14_async_usage/)
import asyncio
asyncio.run(jmcomic.download_album_async('123'))
```

上面的 `download_album`方法还有一个参数`option`，可用于控制下载配置，配置包括禁漫域名、网络代理、图片格式转换、插件等等。

你可能需要这些配置项。推荐使用配置文件创建option，用option下载本子，见下章：

### 2. 使用option配置来下载本子

1. 首先，创建一个配置文件，假设文件名为 `option.yml`

   该文件有特定的写法，你需要参考这个文档 → [配置文件指南](./assets/docs/sources/option_file_syntax.md)

   下面做一个演示，假设你需要把下载的图片转为png格式，你应该把以下内容写进`option.yml`

```yml
download:
  image:
    suffix: .png # 该配置用于把下载的图片转为png格式
```

2. 第二步，运行下面的python代码

```python
import jmcomic

# 创建配置对象
option = jmcomic.create_option_by_file('你的配置文件路径，例如 D:/option.yml')
# 使用option对象来下载本子
jmcomic.download_album(123, option)
# 等价写法: option.download_album(123)
```

### 3. 使用命令行
> 如果只想下载本子，使用命令行会比上述方式更加简单直接
> 
> 例如，在windows上，直接按下 win+R 键，输入`jmcomic xxx`就可以下载本子。

示例：

下载本子123的命令

```sh
jmcomic 123
```
同时下载本子123, 章节456的命令
```sh
jmcomic 123 p456
```

命令行模式也支持自定义option，你可以使用环境变量或者命令行参数：

a. 通过命令行--option参数指定option文件路径

```sh
jmcomic 123 --option="D:/a.yml"
```

b. 配置环境变量 `JM_OPTION_PATH` 为option文件路径（推荐）

> 请自行google配置环境变量的方式，或使用powershell命令:  `setx JM_OPTION_PATH "D:/a.yml"` 重启后生效

```sh
jmcomic 123
```

### 4. 查看本子详情（jmv 命令）

> `jmv` 命令用于快速查看本子详情，不做下载。
> 
> **适用场景**：在某些网站上看到一串*神秘车号*，想快速看看具体是啥本子。此时只需copy原文本，按下 win+R，输入`jmv [粘贴内容]`即可
>
> 支持从任意文本中提取数字作为车号，方便直接粘贴各种格式的车号。

示例：

```sh
# 直接输入车号
jmv 350234

# 从混合文本中提取数字（提取出 350234）
jmv 350谁还没看过234

# 指定option文件（也支持环境变量，用法同上）
jmv 350234 --option="D:/a.yml"

# -y 参数：执行完毕后直接退出，无需按回车确认
jmv 350234 -y
```

输出效果：

```text
🔍 正在查询 禁漫车号 - [350234] 的详情...

──────────────────────────────────────────────────
  📖 标题:  xxx
  🆔 ID:    JM350234
  🔗 链接:  https://18comic.vip/album/350234/
  ✍️ 作者:  Author1, Author2
──────────────────────────────────────────────────
  📅 发布日期:  2022-06-15
  📅 更新日期:  2023-01-01
  📄 总页数:    50
  👀 观看:      2M
  ❤️ 点赞:     77K
  💬 评论:      9801
──────────────────────────────────────────────────
  🏷️ 标签:  标签1, 标签2, ...
  🎭 人物:  角色A, 角色B, ...
  📚 作品:  作品1, 作品2, ...
──────────────────────────────────────────────────
  📑 章节 (2):
     第1話  上  (id: 350234)
     第2話  下  (id: 350235)
──────────────────────────────────────────────────

[运行结束] 请按回车键关闭窗口... (下次运行可附加 -y 参数跳过确认)
```



## 进阶使用

请查阅文档首页 → [jmcomic.readthedocs.io](https://jmcomic.readthedocs.io/zh-cn/latest)

或者查看github仓库的文档 → [github-repo-docs](https://github.com/hect0x7/JMComic-Crawler-Python/blob/master/assets/docs/sources/tutorial/0_common_usage.md)

（提示：jmcomic提供了很多下载配置项，大部分的下载需求你都可以尝试寻找相关配置项或插件来实现。）

## 项目特点

- **绕过Cloudflare的反爬虫**
- **实现禁漫APP接口最新的加解密算法 (1.6.3)**
- 用法多样：

  - GitHub
    Actions：网页上直接输入本子id就能下载（[教程：使用GitHub Actions下载禁漫本子](./assets/docs/sources/tutorial/1_github_actions.md)）
  - 命令行：无需写Python代码，简单易用（[教程：使用命令行下载禁漫本子](./assets/docs/sources/tutorial/2_command_line.md)）
  - Python代码：最本质、最强大的使用方式，需要你有一定的python编程基础
- **支持 Async 和 Sync 两套 API**
- 支持**网页端**和**移动端**两种客户端实现，可通过配置切换（**移动端不限ip兼容性好，网页端限制ip地区但效率高**）
- 支持**自动重试和域名切换**机制
- **可配置性强**

  - 不配置也能使用，十分方便
  - 配置可以从配置文件生成，支持多种文件格式
  - 配置点有：`请求域名` `客户端实现` `是否使用磁盘缓存` `同时下载的章节/图片数量` `图片格式转换` `下载路径规则` `请求元信息（headers,cookies,proxies)` `中文繁/简转换` 
    等
- **可扩展性强**

  - 支持自定义本子/章节/图片下载前后的回调函数
  - 支持自定义类：`Downloader（负责调度）` `Option（负责配置）` `Client（负责请求）` `实体类`等
  - 支持自定义日志、异常监听器
  - **支持Plugin插件，可以方便地扩展功能，以及使用别人的插件，目前核心内置插件有**：
    - `登录插件`、`只下载新章插件`、`导出收藏夹为csv文件插件`
    - `合并所有图片为pdf文件插件`、`合并所有图片为长图png插件`
    - `压缩文件插件`、`自动获取浏览器cookies插件`、`订阅更新插件`等

## 使用小说明

* 推荐使用 **Python 3.12+**，目前最低兼容版本为3.9。
  > 注意：Python 3.9 及更早版本皆已于 2025 年彻底结束官方生命周期 (EOL)，使用3.9及以下随时有可能遇到第三方库不兼容的问题。

* 个人项目，文档和示例会有不及时之处，可以Issue提问。

## 项目文件夹介绍

* .github：GitHub Actions配置文件
* assets：存放一些非代码的资源文件

  * docs：项目文档
  * option：存放配置文件
* src：存放源代码

  * jmcomic：`jmcomic`模块
* tests：测试目录，存放测试代码，使用unittest
* usage：用法目录，存放示例/使用代码

## 感谢以下项目

### 图片分割算法代码+禁漫移动端API

<a href="https://github.com/tonquer/JMComic-qt">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt&theme=radical" />
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
    <img alt="Repo Card" src="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
  </picture>
</a>
