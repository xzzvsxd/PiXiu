<p align="center">
  <img src="logo.png" alt="PiXiu Logo" width="200"/>
</p>

<h3 align="center">貔貅 - 基于FinGLM的金融领域问答系统</h3>

## 关于项目

这是一个人工智能大模型方向的本科毕业设计，旨在基于FinGLM构建一个可上传PDF年报数据、Word年报数据、图片以及文字的前后端问答系统。  
项目使用Python3.11并在Windows11系统上测试运行正常。  
建议在24GB显存条件下运行本项目。  
测试硬件环境为：  
CPU - 13th Gen Intel(R) Core(TM) i9-13900F  
GPU - NVIDIA GeForce RTX 4090 (24GB)

## 如何使用

1. 克隆仓库 (请提前 [安装Git LFS](https://docs.github.com/zh/repositories/working-with-files/managing-large-files/installing-git-large-file-storage)，然后运行并使用git clone)
2. 安装依赖 (pip install -r requirements.txt)
3. 下载模型与数据集 (Models及FineTune/data/alltxt)
4. 运行项目
- 前端 (python3 run.py)
- 后端 (python3 PiXiu.py)

### 下面是一些可能需要注意的事项：

#### 图片问答功能
需要在FineTune/Config.py中配置DASHSCOPE_API_KEY。  
api key可以从阿里云通义千问Qwen-VL-Max页面获取。

#### 自行添加年报数据集
本项目可以通过逐步运行Prepare_Data目录下的序号py文件来进行数据扩充，获取年报数据集，然后通过手动上传进系统来扩充系统的数据集。  
有心的开发者可以自行写出一个联网整合版本。


#### PyCharm 设置

为了优化 PyCharm 的性能，请将以下目录从索引中排除：

- `/FineTune/alltxt`
- `/FineTune/allpdf`
- `/FineTune/pdf_docs`

这些目录中包含 `.pycharmignore` 文件作为标记。在 PyCharm 中，右键点击这些目录，选择 "Mark Directory as" > "Excluded" 来排除它们。

## TODO

- [x] First Commit
- [ ] 自动联网搜索年报数据
- [ ] 支持生成相关的金融数据统计图
- [ ] So on...

## 鸣谢

FinGLM (https://github.com/MetaGLM/FinGLM)  
freegpt-webui (https://github.com/ramon-victor/freegpt-webui)  
gpt4free (https://github.com/xtekky/gpt4free)  
ChatGLM2 (https://github.com/THUDM/ChatGLM2-6B)  
XuanYuan (https://github.com/Duxiaoman-DI/XuanYuan)  
Qwen (https://github.com/QwenLM/Qwen-VL)


## 许可证

本项目采用 [GNU通用公共许可证第3版](LICENSE) 。

这意味着你可以自由地使用、修改和分发这个软件，但是任何衍生作品也必须在GNU GPL v3下发布。  
完整的许可证文本可以在LICENSE文件中找到。