# 路线规划对比工具 (Route Comparison Tool)

这是一个基于 Flask 的 Web 应用，用于获取、分析和可视化来自不同地图服务提供商（Google, HERE, OSRM）的车辆路线。用户可以指定一个地理区域，应用会随机生成起终点对，并同时请求三个平台的路线，最终在交互式地图上展示结果并进行数据对比。

## ✨ 主要功能

- **多服务对比**: 同时从 Google Directions API, HERE Routing API, 和 Project OSRM 获取路线。
- **可视化展示**: 使用 Mapbox GL JS 在交互式地图上以不同颜色渲染各家服务的路线。
- **数据统计**: 计算并展示每条路线的距离、预估时长，以及 HERE 和 OSRM 路线与 Google 路线的重叠率。
- **详细导航**: 显示每个路线规划的详细转弯导航指令。
- **灵活区域选择**: 支持选择预设的城市区域（如斯图加特、迪拜等），或在地图上动态绘制自定义边界框（Bounding Box）。
- **策略选择**: 支持选择不同的路线规划策略，如“最短距离”或“最快时间”。

## 🛠️ 技术栈

- **后端**: Flask, Gunicorn
- **地理空间处理**: GeoPandas, Shapely, Pyproj
- **API 客户端**: googlemaps, requests
- **前端**: 原生 JavaScript, Mapbox GL JS, Bootstrap 5
- **环境管理**: Python, pip, venv

## 🚀 安装与运行

请按照以下步骤在你的本地环境中设置并运行此项目。

### 1. 克隆仓库

```bash
git clone <你的仓库URL>
cd <仓库目录>
```

### 2. 创建并激活虚拟环境

使用虚拟环境可以隔离项目依赖，避免与其他项目冲突。

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate
```

### 3. 安装依赖

项目的所有依赖都记录在 `requirements.txt` 文件中。

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

为了让应用能够访问地图服务的 API，你需要提供相应的 API 密钥。

a. 在项目根目录下创建一个名为 `.env` 的文件。

b. 将以下内容复制到 `.env` 文件中，并替换成你自己的密钥。

```env
# 用于 Google Directions API
GOOGLE_ROADS_API_KEY="YOUR_GOOGLE_API_KEY"

# 用于 HERE Routing API
HERE_MAP_DATA_API_KEY="YOUR_HERE_API_KEY"

# 用于 Mapbox 地图渲染
MAPBOX_ACCESS_TOKEN="YOUR_MAPBOX_ACCESS_TOKEN"
```

### 5. 运行应用

本项目包含一个 Flask 开发服务器，可以直接运行。

```bash
flask run
```

应用启动后，在浏览器中打开 `http://127.0.0.1:5000` 即可访问。

## 📖 使用说明

1.  **选择区域**: 在左侧边栏，你可以从下拉菜单中选择一个预设的城市，或者点击 "Draw on Map" 按钮在地图上绘制一个矩形区域。
2.  **选择策略**: 选择你希望的路线规划策略（例如 "Shortest"）。
3.  **开始对比**: 点击 "Compare Routes" 按钮。后端将开始并发请求三个 API 并处理数据，你可以在下方的日志窗口看到实时进度。
4.  **分析结果**:
    -   处理完成后，地图上会显示所有生成的路线。
    -   你可以使用 "Select Route Pair" 下拉菜单单独查看某一对起终点的路线。
    -   "Statistics" 面板会显示选中路线对的详细数据，包括距离、时长、重叠度和导航指令。
    -   你可以通过复选框控制各地图服务路线的显示和隐藏。

## 📝 许可证

本项目采用 MIT 许可证。