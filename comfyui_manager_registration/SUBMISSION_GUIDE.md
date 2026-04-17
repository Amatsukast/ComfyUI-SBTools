# ComfyUI Manager 登録手順

## 準備完了 ✅

以下のファイルが準備されています：
- `pyproject.toml` - リポジトリルートに配置済み
- `custom-node-list-entry.json` - PRに使用するエントリ

---

## PR提出手順

### Step 1: ComfyUI-Managerリポジトリをフォーク

1. https://github.com/ltdrdata/ComfyUI-Manager にアクセス
2. 右上の「Fork」ボタンをクリック
3. あなたのGitHubアカウントにフォーク

### Step 2: custom-node-list.json を編集

1. フォークしたリポジトリで `custom-node-list.json` を開く
2. ファイルの最後（JSONの配列内）に、`custom-node-list-entry.json` の内容を追加
3. **重要**: カンマの位置に注意（前のエントリの後にカンマが必要）

**追加箇所の例:**
```json
{
    "custom_nodes": [
        {
            "author": "existing",
            "title": "Existing Node",
            ...
        },
        {
            "author": "Amatsukast",
            "title": "ComfyUI-SBTools",
            "reference": "https://github.com/Amatsukast/ComfyUI-SBTools",
            "files": [
                "https://github.com/Amatsukast/ComfyUI-SBTools"
            ],
            "install_type": "git-clone",
            "description": "Workflow toolkit for ComfyUI. Includes BiRefNet background removal, dynamic prompt/image variable system for batch generation, chroma key tools, and more utilities."
        }
    ]
}
```

### Step 3: PRを提出

1. 変更をコミット
   - Title: `Add ComfyUI-SBTools`
   - Description: `Adding ComfyUI-SBTools - workflow toolkit with background removal, prompt/image variable system, and utility tools.`
2. Pull Requestを作成
3. ltdrdata（メンテナー）のレビュー待ち

### Step 4: 動作確認（推奨）

PR提出前に、以下で動作確認：
1. ComfyUI Managerで「Use local DB」をオン
2. 「Install custom nodes」ダイアログでエラーがないか確認

---

## マージ後

- ComfyUI Managerの検索で「SBTools」が表示される
- ユーザーはワンクリックでインストール可能
- 更新は自動的に反映（あなたが`git push`するだけ）

---

## 注意事項

### Description更新
`description`や`title`を変更したい場合は、再度PRが必要

### バージョン管理
- `__init__.py`の`__version__`を更新
- `pyproject.toml`の`version`も同期
- CHANGELOGを更新

### トラブルシューティング
- JSON構文エラー: カンマの位置を確認
- リポジトリが見つからない: `files`のURLを確認
- インストールエラー: `requirements.txt`を確認

---

## 参考リンク

- ComfyUI Manager: https://github.com/ltdrdata/ComfyUI-Manager
- カスタムノードリスト: https://github.com/ltdrdata/ComfyUI-Manager/blob/main/custom-node-list.json
