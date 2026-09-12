# Repository Forbxy

## 仓库安装方式 1
1. Kodi-设置-文件管理(或者视频，音乐等任意可以添加源的地方)-添加源，点击浏览,添加网络地址,协议选择WEB服务器目录(HTTPS),服务器地址填kodi8.com,点击确定
2. Kodi-设置-插件-从 zip 安装，选择[https://kodi8.com:443/]([https://kodi8.com:443/) ,忽略前面的文件夹，一直往下翻，找到并安装repository.forbxy-xxx.zip或repository.forbxy.ghproxy-xxx.zip  

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
- [script.controller.switcher](https://github.com/forbxy/script.controller.switcher)  
  遥控器适配插件,适配了大量遥控器,同时支持自定义按键,可用于将筛选页面和其他功能绑定到遥控按键上
- [plugin.video.filteredmovies](https://github.com/forbxy/plugin.video.filteredmovies)  
  电影剧集筛选页面和一些常用功能的接口实现
- [skin.cpm.estuary.search](https://github.com/forbxy/skin.cpm.estuary.search)  
  与筛选页搭配使用的官方 estuary 皮肤修改版
- [vfs.stream.fast](https://github.com/forbxy/vfs.stream.fast)  
  Kodi WebDAV, HTTP VFS 实现，支持打开 ISO 文件
- [plugin.service.emby-next-gen 12.3.7.2](https://github.com/forbxy/plugin.video.emby.vfs)  
  与 vfs.stream.fast 适配的 Emby Next Gen 插件修改版(老版本仓库)
- [plugin.service.emby-next-gen 12.4.15+](https://github.com/forbxy/plugin.service.emby-next-gen)  
  与 vfs.stream.fast 适配的 Emby Next Gen 插件修改版(新版本仓库)
- [script.gen-ce-boot-animation](https://github.com/forbxy/script.gen-ce-boot-animation)  
  从动图或视频生成CoreELEC 开机动画插件
- [service.watch.track](https://github.com/forbxy/service.watch.track)  
  通过网盘文件同步kodi播放记录
- [plugin.cloudstorage.webdav.refresh](https://github.com/forbxy/plugin.cloudstorage.webdav.refresh)  
  手动刷新 OpenList WebDAV 插件
- [script.emby.nextgen.cleaner](https://github.com/forbxy/script.emby.nextgen.cleaner)  
  清理Emby Next Gen卸载后的残留文件的插件
- [script.iptvsimple.fast](https://github.com/forbxy/script.iptvsimple.fast)  
  为IPTV simple client写入默认流设置来实现快速切台(手动用遥控器设置太麻烦了)

## 注意事项

 - Kodi 的插件仓库并不是实时更新的 (可能是 24 小时更新一次)，如果需要安装最新插件，你可能需要在仓库页手动触发更新仓库。  
 - 仓库中插件的历史版本可以通过访问 [kodi8.com](https://kodi8.com) 下载安装,或者如果你选择的是安装方式1,可以直接从添加的源安装
