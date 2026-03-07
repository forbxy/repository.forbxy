# Repository Forbxy

## 仓库安装方式 1
1. Kodi-设置-文件管理-添加源，路径输入: `https://kodi8.com`
2. Kodi-设置-插件-从 zip 安装，选择刚才添加的源

## 仓库安装方式 2
从 Release 下载插件仓库 zip 文件安装

## 仓库说明
- **repository.forbxy**: 库中插件直接从 GitHub 原始链接下载
- **repository.forbxy.ghproxy**: 库中插件从 gh-proxy.com 转发下载 (GitHub 访问不稳定的地区可以用这个)

## 插件安装
安装完仓库插件后，选择：
Kodi-设置-插件-从库安装-Kodi Forbxy Addon Repository，即可浏览并安装所需插件。

## 插件列表

- [metadata.tmdb.cn.optimization](https://github.com/forbxy/metadata.tmdb.cn.optimization)  
  多线程 tmdb 电影刮削器
- [metadata.tvshows.tmdb.cn.optimization](https://github.com/forbxy/metadata.tvshows.tmdb.cn.optimization)  
  多线程 tmdb 剧集刮削器
- [plugin.video.filteredmovies](https://github.com/forbxy/plugin.video.filteredmovies)  
  电影剧集筛选页面和一些常用功能的接口实现
- [skin.cpm.estuary.search](https://github.com/forbxy/skin.cpm.estuary.search)  
  与筛选页搭配使用的官方 estuary 皮肤修改版
- [vfs.stream.fast](https://github.com/forbxy/vfs.stream.fast)  
  Kodi WebDAV, HTTP VFS 实现，支持打开 ISO 文件
- [plugin.video.emby.vfs](https://github.com/forbxy/plugin.video.emby.vfs)  
  与 vfs.stream.fast 适配的 Emby Next Gen 插件修改版
- [plugin.cloudstorage.webdav.refresh](https://github.com/forbxy/plugin.cloudstorage.webdav.refresh)  
  手动刷新 OpenList WebDAV 插件

## 注意事项

Kodi 的插件仓库并不是实时更新的 (可能是 24 小时更新一次)，如果需要安装最新插件，你可能需要在仓库页手动触发更新仓库。