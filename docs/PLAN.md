# 時計のゴーレム — 制作計画

参考：`reference/concept_front.png`（正面のコンセプト）、`reference/turnaround_sheet.png`（三面図・腕と脚の詳細・時計の拡大・大きさ）。

## 決まっていること（2026-10-19）

| 項目 | 内容 |
|---|---|
| 使う先 | Godot 4（`.glb` で渡す） |
| ポリゴン数 | 上限なし・減らさない（PC 向け。2026-10-19 に 3 万 → 10 万 → 20 万 → 上限なし）。遠くの軽い版は Godot が読み込み時に自動で作る。重すぎたら最後に軽い版を別に作る |
| 大きさ | 高さ 3.5 m（三面図の「約3.5m」） |
| 横・背面 | 三面図に合わせる |
| 浮かぶ破片 | 含めない |
| アニメーション | 待機だけ |
| 輪郭線 | Godot 側で付ける（材質の `next_pass`、裏返した殻）。モデルには入れない |

## 確かめ方

- 比較画像はトゥーン調で描く（Cycles で光を 3 段に分け、Freestyle で輪郭線とひびの線。ひびと岩の面の境目には線の印を付ける）。灰色の簡易表示は `--flat`。

- 三面図の各図を切り出して影絵にし（`tools/ref_mask.py`）、モデルを同じ縮尺・同じ向きの正投影で写した影絵と重ねる（`golem/views.py`、`golem/compare.py`）。
  - 重なりの割合（IoU）を数え、`review/<段階>/report.json` に残す。
  - `review/<段階>/compare_*.png`：左から参考、モデル、差（緑＝一致、赤＝足りない、青＝はみ出し）。
- 高さごとの左右の端を数字で比べる：`tools/profile_diff.py <front|side|back>`。
- 寸法の読み取りには目盛り付きの画像を使う：`tools/ref_grid.py`。

## ステップ

| # | 内容 | 確認の目安 | 状況 |
|---|---|---|---|
| 0 | 準備：bpy 5.2.2（画面なしでレンダリング）、1 コマンドで作る→写す→比べる、GitHub Actions | ローカルと CI で同じ結果 | 済 |
| 1 | 参考を測る：縮尺（1 px = 7.2 mm）、各部の位置、色（k-means）。`spec/golem.yaml` | — | 済 |
| 2 | 荒い形：基本形で全体の比率 | 3 方向とも IoU 0.85 以上 | 済（正面 0.873、横 0.858、背面 0.850）。利用者の確認済み |
| 3 | 胴の時計：柱の溝、柱頭、X の飾り、上の飾りとアーチ、文字盤（ローマ数字の画像）、砂時計の枠 | 正面の時計部の拡大比較 | 済（`review/case/`）→ **確認待ち** |
| 4 | 白い殻と岩：一続きの岩の塊の表面を不規則な面・尖り・へこみ・ひびに割る。白い石はその上の厚い殻で、不規則に剥がれて岩が見える（2026-10-19 作り直し：石を貼り合わせた形はやめた） | 拡大の比較 | 作り直し中 |
| 5 | 腕・脚・歯車・重り・背中の仕掛け（大歯車、柱、3 本の振り子）。手首は爪ではなく、割れてめくれた茶色い殻と溝付きの台座 | 腕と脚の詳細図との比較 | 作り直し中 |
| 6 | 色と線：材質は単色（色は参考から拾う）＋文字盤の画像。ひびと岩の境目の線は頂点の色に入れる。焼き込みのテクスチャは使っていない | Godot の画面 | 済 |
| 7 | 見た目：Blender はトゥーン（Cycles＋Freestyle）、Godot はトゥーンのシェーダーと輪郭線（裏返した殻、`next_pass`） | 参考と並べる | 済 |
| 8 | リグと待機：骨 25 本、部品の名前から重みを決めて 1 つのメッシュに。待機 6 秒のループ（胸の呼吸、腕、ランタン・重り・振り子の揺れ、長針が 1 周） | 動きの確認 | 済 |
| 9 | Godot：`scripts/export_godot.py` で `godot/golem/golem.glb`、`godot/golem_scene.tscn` で表示。`godot/tools/check.gd` で読み込みと撮影 | Godot 4.4.1 で確認 | 済（`review/godot_idle.png`） |
| 10 | まとめ：三角形の数、テクスチャ、骨の数、確認の結果 | — | |

## ポリゴン数

上限なし。`review/<段階>/report.json` に部品のまとまりごとの数を出す。

## 三面図どうしの食い違い（作るときの判断）

**食い違うときは正面図を基本にする**（クローズアップや側面図より正面図。2026-10-19 利用者）。

- 柱の下の金の飾り：正面図では高さ 0.6 m あたりで終わるが、側面図では 0.25 m まで垂れている。正面図に合わせて 0.6 m。
- 籠手の大きな歯車：正面図でも側面図でも正面向きに見える。外側の斜め前（35°）に向けた。詳細の段階で見直す。
- 背面図には正面と同じような柱・台座・盾形の土台に載った大歯車があるが、側面図では背中はそこまで出ていない。背面図に合わせ、柱は体に寄せて奥行きを薄くした。このため細部の段階の横の IoU の目標は 0.84（荒い形は 0.85）。

## 動かし方（Godot）

```sh
EGL_PLATFORM=surfaceless .venv/bin/python scripts/export_godot.py --out godot/golem   # glb を作る（約 4 分、約 85 MB）
godot --headless --path godot --import                                              # 読み込み
godot --headless --path godot --script res://tools/check.gd                         # 数の確認
xvfb-run godot --rendering-driver opengl3 --path godot --script res://tools/check.gd -- --shot=out.png   # 撮影（--close、--at=秒）
```

glb は大きいので Git には入れない（作り直せる）。三角形は約 72 万。重い場合は Godot の読み込み設定で LOD を使うか、軽い版を別に作る。

## 動かし方

```sh
scripts/setup.sh                         # .venv に bpy などを入れる（Mesa も）
EGL_PLATFORM=surfaceless .venv/bin/python scripts/build.py --stage case   # 段階：blockout, case
```

`out/golem_<段階>.blend` ができ、`review/<段階>/` に比較画像（`compare_*`）、拡大の比較（`detail_*`）、斜めの画像（`three_quarter*`）、`report.json`（IoU、三角形の数を予算のまとまりごとに）が出る。IoU が目標より低いと終了コード 1。

## 2D 版（カットアウト、2026-10-24）

正面のコンセプト（`reference/concept_front.png`）を部品に切り分け、Godot 4 の 2D で骨組みのように動かす。待機だけ。

| 部品 | 動き |
|---|---|
| 胴（脚より上すべて） | 腰を支点に呼吸（6 秒で 1 回、上端が約 15 px 上がり、横にも少し膨らむ） |
| 腕（左右） | 肩を支点に呼吸に少し遅れて外へ 2.5° |
| 手首の重り 6 個・胴の下の重り | 遅れて揺れる（6〜9°） |
| 時計の針 | 0.5 秒ごとに 1 目盛り刻む（スクリプト `golem2d.gd`） |
| 砂時計 | 流れる砂粒、上下の膨らみのきらめき、上の光の明滅 |
| 浮いた岩のかけら 8 個 | ふわふわ上下（12 px）と回転（14°） |
| 脚・地面の影 | 動かない |

- 切り分け：`python -m golem2d.cut --out godot2d/parts`（部品の形と支点は `golem2d/parts.py`）。白い紙を透明にし、動く部品の下に隠れていた所は周りの色で塗り足す。胴と脚の境目は 762〜800 px で胴が薄れていくので、呼吸しても継ぎ目が出ない。
- シーン：`python -m golem2d.scene --project godot2d` で `godot2d/golem2d.tscn`（AnimationPlayer の `idle`、0.25 秒ごとのキー。エディタで直せる）。
- 確認：`godot --headless --path godot2d --script res://tools/check.gd`。録画は `--write-movie out/f.png --fixed-fps 30 --quit-after 180`。動画は `review/2d/idle.mp4`。
- 2026-10-24：動きが分かるよう全体に約 2.5 倍に大きくした（利用者）。腕の下の塗り足しも 14 → 22 px に広げた。
- 0 コマ目は元の絵とほぼ同じ（平均の差 0.8/255。残りは針・浮いたかけら・光）。
