# 工具与维护来源

0.3.54同时核验发布场景和Prefab，生成前核对资产归属与人工修改，失败路径回退已写产物并恢复临时配置。离线验收绑定本轮引擎证据，旧报告需重新验收。安装包提供 `--upgrade` 和 `--recover`，调用见 INSTALL.md。

0.3.52修正并行工程串文件：工具目录只读，安装器默认workspace为工程/.ui_pipeline并写project_root；C#读取时核对工程与路径，ConfiguredUITrial在写报告前检查任务路径。PSD预览脚本改从tool_workspace读取。MCP客户端要求完整实例ID及工程路径并先验证。旧共享配置需按INSTALL.md迁移；拒绝旧配置不是自动迁移完成。task目录仍由AI按trial.md初始化，同工程写操作串行。这些检查约束已接入入口，不是操作系统权限沙箱。
本skill附规则和模板，不包含Unity安装或模型账号。0.3.47-trial 完整分发包同时附 runtime 工具目录和 install_trial.py；安装器写本机 local.config.json 的 tool_workspace。单独的 skill zip 仍依赖外部工具工作区。首次使用见 trial.md 和完整包 INSTALL.md，跨机器不沿用作者的路径。

工具包含scripts/pipeline_common.py、ui_package_contract.py、prepare_stage2_unity.py、setup_unity.py与unity_tools/Editor/PreciseUIBuilder.cs、CleanUIExport.cs等。先核对入口，传本次数据；旧案例RunCurrent/RunAll不是新图验收器。确切边界见execution.md的工具表。缺少工具时说明具体缺口，检查目标工程已有能力，不复制旧页面业务规则。

新图验证编排可用 ConfiguredUITrial.Run(config)，通过工程工作区active_trial.json指定输入；离线证据用scripts/verify_ui_trial.py。这些工具复用上述导入、合成、发布入口。Python图像部分需要Pillow/numpy/OpenCV等当前工作区依赖，Unity部分需要uGUI/TMP；连接MCP是本机控制方式，可替换为用户环境已有编辑器执行方式。技能包没有附带这些安装或图像服务账号。

0.3.1工具支持可选外观版本声明（素材visual_variant、实例required_visual_variant）、保留正文的text_runs颜色区段、原生TMP字重/字面扩张/描边/投影，以及panel配方的bevel/gloss。prepare_stage2_unity调用共用契约检查后导出；旧输入未声明新样式时保留原行为。参数要按目标尺寸校准，不将某案例的数值或立体效果默认应用到所有页面。重复导入检查按实际根Canvas识别可忽略的派生尺寸。

分享zip不含local.config.json。完整试用包的安装器配置随包 runtime 路径；assets/release.json包含工具指纹，完整包另有 manifest.json 校验。路径迁移测试不能代替另一台电脑和真实项目验证。

维护源是工具工作区scripts/templates/PROCESS.md、NEW_IMAGE_RUN.md和DESIGN_REVIEW.md。workflow.md/execution.md/design_review.md是发布副本，更新源时同步；历史项目链接只作来源说明。状态模板维护源为scripts/templates/state_inventory.json，经standard/templates发布到skill；其他模板沿原发布入口维护。发布文件哈希见assets/release.json。生成素材须复制到项目，不只留临时目录。

0.3.3增加可选effects_profile及其验收哈希、元素归属/覆盖/输入检查。unity_tools/Editor/UIEffectAuthoring.cs复用原生Image创建独立材质；UIProceduralEffect.shader目前只支持光芒与四角星闪光，支持uGUI裁切，未实现通用粒子或任意动画重建。生命周期接入现有页面控制器，不能因本例默认所有特效都在弹窗时隐藏。effects_inventory.json是设计清单，具体执行配置需选择实现并补足参数。记录工具在Editor里，交付UI不挂录制或生成组件。

0.3.5新增ui_visual_metrics.py及visual_metrics_profile.json：按固定局部输出PSNR、SSIM、CIEDE2000色差、边缘距离和合成错误对照；透明输入须先按明确背景合成，尺寸不一致拒绝。依赖Pillow/numpy/OpenCV/scikit-image，库版本与输入哈希随报告保存。没有视觉总分、通用通过阈值或自动调参循环。工具能算不代表指标已在其他风格上校准。

0.3.10新增工作区 `scripts/export_git_ui_snapshot.py`：从 Git 对象与已校验的 LFS 内容导出固定版本，不切当前分支。当前适配的是 OH 的 `client/` 仓库布局；接其他布局须先适配路径参数，不能称任意 Unity 项目通用。它追直接 GUID/着色器引用并接受显式依赖，不能自动发现所有字符串加载和启动注册；需补查 TMP Resources、备用字体等。`unity_tools/Editor/OHPreviewEnvironment.cs` 小幅提取既有 OH 相机与离屏截图入口，可传源相机 Prefab；案例生成器、文件指令桥和测试数据只属于案例，不当作另一项目的一键工具。

0.3.11：新布局显式声明image_fit/filter_mode；UIImportPolicy复用原导入入口，source读取独立工程原纹理采样设置。preflight_ui_layout.py在Unity前检查输入；ConfiguredUITrial逐图检查并输出coverage.json。UIEnvironmentBootstrap先完成TMP资源导入，EnsureFont不再启动未完成的异步导入。UITrialPreview提供当前试验场景入口；setup_unity仅在项目声明URP时复制OH专用相机适配器。历史快照缺失LFS下载使用输出目录.lfs-cache，禁止输出缓存落在源仓库内；仍保留SHA256验证，不改源工作树/分支。详见execution.md新输入与环境检查。

验证边界：隔离LFS缓存已通过本机HTTP下载测试，源仓库文件哈希无变化；file://传输在该缓存覆盖配置下的试验失败，不宣称已支持。干净发布在batchmode先保存无名场景到生成目录的SessionScenes，保留原场景内容，再创建发布场景；交互编辑器有无名场景时先要求保存，不静默丢弃。

0.3.12：ui_review_gate.py负责最小独立复核包、输入哈希失效和sample/final检查；workflow_version=2的原Build入口在assembly前要求有效sample。ui_visual_relations.py对实际引擎观察值检查关系，UIWorkflowChecks负责观测和调用；ConfiguredUITrial接入默认状态。新工具不替代视觉判断，也不认证reviewer身份。完整参数与边界见mechanisms.md。

0.3.13：compile_ui_asset_choices.py复用content_rect，调用ui_package_contract.place_content将主体目标范围换算为等比图片框；原Alpha/文件不裁切、不改色。UISampleBatch是固定静态图片样本入口，接受layout/output/folder作业，复用Build/CapturePrefab，输出实际矩形检查和干净Prefab。只处理静态Image/Group，不宣称状态、字体、交互或动画通过。选图及主体边界判断仍需独立复核，见mechanisms.md。

0.3.14：UIEnvironmentBootstrap.IsReady 同时检查 TMP Settings 与 Distance Field Shader；RealButtonValidation 和 PreciseUIBuilder 复用此环境要求，缺设置时先完成独立初始化。新增可选 font_material_path 复用原 TMP 材质，要求与字体图集一致。代表字形的实际渲染仍是必要证据。奖励组件与其状态窗口仅是案例，不冒充通用业务组件生成器。

0.3.15：annotate_ui_reference.py 是只读标注草稿工具，AI选区后辅助测量浅色字面/有界素材匹配，读取原Prefab的基础TMP设置，并从同一JSON生成覆盖图与清单。不是自动语义检测或完整Prefab继承解析器；详见auto_annotation.md。本轮不生成或修改Unity对象。

0.3.16：新增标注配置换算、独立副本组装与单轮字形校准入口；ConfigureTMP支持显式顶部/底部顶点渐变。框类型、图像伸缩策略、自动字号与最终字面残差分开记录，详见auto_annotation.md。未解析任意原Prefab运行规则，使用前仍需指定已理解的目标组件。

0.3.18：UIAnnotationVariant 可在副本中复用原组合控件/指定视觉组件，按源fileID应用实例覆盖；每个对象一次提交关联字段，避免旋转中间归一化。新增绑定类型和效果开关对照，详见auto_annotation.md。依赖和业务含义仍需调用方准备；不自动解析整个项目的Prefab继承或运行规则。


0.3.20：设计规范库使用 scripts/build_design_library.py --library <目录>，依赖PyYAML，从描述文件生成HTML和校验报告。extract_design_annotations.ps1仅辅助读标注，需Windows PowerShell 5.1；OCR结果仍须对照原资料。工具不自动匹配/修改Unity或批准规则。

0.3.23：UIDesignComponentRecipe（Editor）复用已核对的源子树，组合文字参数、源布局、项目TrueShadow预设和明确的尺寸策略；只验证过普通方形图标+数量。Fill/SetDisplaySize后须Audit，失败不得交付。不存在通用任意组件一键生成承诺；项目关联、已验状态和缺项见design_library.md与对应实现描述。


0.3.25：UIDesignComponentRecipe增加直接父容器的PlaceCentered/PlaceWithOffset/AuditPlacement；默认中心锚点/轴心及零偏移，反查实际Rect中心差，拒绝活动LayoutGroup冲突。非零偏移需显式依据；依据有效性仍由设计复核判断，不靠字符串认证。组件内部Audit与容器Audit分别执行。

0.3.27：图标尺寸按项目确认的离散档位选择，按图标实际框和实例/Canvas缩放换算；区分参考画布尺寸与最终设备像素，透明主体范围不得隐式trim。OH档位记录在OH项目设计库，不复制为其他项目的默认值。验证仅更新维护源、YAML生成网页与发布skill，没有改Unity或组件布局。


0.3.34：`scripts/compile_component_declarations.py --profile <项目配置> --profile-sha256 <调用方冻结的哈希> --input <模型声明> --output <新文件>` 只编译合法数据，不执行Unity。项目配置提供资源与范围；宽度可选离散档位，不默认OH值。通用入口 `PreciseUI.UIRestrictedComponentSample.Run(packetPath, expectedPacketHash, expectedProfileHash, expectedProjectRoot, outputPrefab, reportPath)` 在已有编辑器的预览场景中复用既有方形道具＋数量组件，二次核验哈希，执行Fill/SetDisplaySize/PlaceCentered/Audit，仅输出新的局部Prefab。调用方负责授权范围与输出目录、素材选择和实际渲染审查；完整页面、其他组件、业务与动画未由这个适配器覆盖。依赖校验不等于操作系统沙箱。项目更换实现时需提供适配器，不复制OH原参数。

该样本工具显式记录自己的Canvas参考尺寸；截图需检查屏幕中的实际框尺寸与零偏移，不能只验证局部84等数值。UIDesignComponentRecipe.Build移除了无范围的AssetDatabase.SaveAssets，保留目标Prefab保存，不保存其他dirty资产。试验通过范围与工具失败记录见validation.md。

0.3.35：ui_review_gate.py新增schema2按共享配置和当前阶段绑定，其他阶段单独变更不废弃当前复核；相关输入或阶段变更仍拒绝，旧schema1保守兼容。inspect_ui_image_styles.py按固定源SHA与唯一节点名读取Image字段，不输出RectTransform/页面坐标，缺失或歧义拒绝；共享解析位于unity_serialized_fields.py，纯标准库，无Unity/第三方Python依赖，但仍需程序阶段提供源Prefab。它不是权限沙箱或完整Prefab继承解析。门槛回归3项、字段读取2项通过；新增环境说明明确艺术交接无需Unity，参数编译虽无需运行Unity仍依赖程序项目文件。工具工作区仍是显式依赖，未交付免安装执行服务。


0.3.36：`verify_observed_layout` 选择布局回查；引擎导出画布坐标、父级、图片策略与素材哈希，`ui_visual_relations.py` 比对声明并支持内容区关系，`ui_review_gate.py` 可生成全页覆盖局部。详细字段和边界见 workflow.md。离线脚本回归通过；本次变更的 Unity 源码未编译或运行，必须先做最小样本，不可冒称引擎通过。机器不能识别任意语义错图。


0.3.37：`PreciseUIBuilder.SetConfigPath(path)` 可为当前调用设置配置，完成后 `SetConfigPath(null)`；配置 `generated_assets` 指定 Assets 下生成目录，`Build(layout, folder, reportPath)` 指定工作区内报告。`scripts/install_ui_tools.py --project ... --plan ... --backup ...` 按明确映射及源/目标哈希备份安装已存在 Editor 工具。绑定组件通过独立预览场景处理含临时根的 Prefab，临时非退化画布下审计后仍须保存重载并渲染检查。ConfiguredUITrial 的可选 fonts 分支尚调用全局 SaveAssets，当前使用已有字体、fonts 留空。验证见 validation.md。


0.3.38：`scripts/inspect_sprite_bounds.py` 按声明的 alpha 阈值输出透明包围范围、比例与来源哈希，不识别语义内容；`compile_annotation_choices.py` 接受显式 content_rect 与视觉依据并使用现有等比换算保留透明边。单页技术小样本在 Unity 生成、重载并截图；颜色阈值测量只是辅助，详细依据见 workflow.md 和案例。


0.3.42：`ui_visual_relations.py`对独立旋转节点按声明矩形、轴心和角度求屏幕包围框，避免拿旋转前宽高误判。零旋转保持原行为；4项回归及本轮实际雨棚引擎观察值通过。尚未支持旋转祖先的复合变换，不扩大为任意布局验证。


0.3.43：`check_ui_scope.py`对调用方提供的归属声明和引擎观察值检查正式导出范围、示例数据依赖、子树、引用及无渲染挂接点。四类归属须由设计证据判断，工具不按亮暗识别宿主。属于已有归属规则的执行/交付检查补足；案例节点与参数不进入通用默认。

0.3.44：`compile_design_styles.py --appearance`新增schema2完整外观描述，保留原schema1文字试作。`UIDesignAppearanceRecipe.cs`作为同一`UIDesignStyleRecipe`的配套实现，应用并反查Image、TMP、明确的TrueShadow和首次创建的静态文字附属层；锁定既有RectTransform，拒绝未知字段及原节点布局参数。PNG烘焙底影、材质关键字和实际阴影组件分别声明；不修改共享材质、Importer或全局阴影设置。参数与素材编号留在项目映射。使用方法与限制见design_library.md“完整外观与仅改表现的修正”；实际引擎和视觉验收仍必需。
