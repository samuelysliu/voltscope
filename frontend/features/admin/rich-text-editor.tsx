"use client";

import { useEffect } from "react";
import Color from "@tiptap/extension-color";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import { TextStyle } from "@tiptap/extension-text-style";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Bold, Heading1, Heading2, Heading3, ImageIcon, Italic, LinkIcon, List, ListOrdered, Pilcrow, Quote } from "lucide-react";
import { Button } from "@/src/components/ui/button";
import { Input } from "@/src/components/ui/input";

export function RichTextEditor({
  value,
  onChange,
  onUploadImage
}: {
  value: string;
  onChange: (value: string) => void;
  onUploadImage?: (file: File) => Promise<string>;
}) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      TextStyle,
      Color,
      Link.configure({ openOnClick: false }),
      Image.configure({ inline: false, allowBase64: false })
    ],
    content: value,
    immediatelyRender: false,
    onUpdate({ editor }) {
      onChange(editor.getHTML());
    },
    editorProps: {
      attributes: {
        class: "article-body min-h-72 rounded-md border border-input bg-background p-4 focus:outline-none"
      }
    }
  });

  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value || "<p></p>", { emitUpdate: false });
    }
  }, [editor, value]);

  if (!editor) return null;

  async function addImage(file: File | undefined) {
    if (!file || !onUploadImage || !editor) return;
    const url = await onUploadImage(file);
    editor.chain().focus().setImage({ src: url, alt: file.name }).run();
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().toggleBold().run()} title="Bold">
          <Bold size={16} />
        </Button>
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().toggleItalic().run()} title="Italic">
          <Italic size={16} />
        </Button>
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().setParagraph().run()} title="Paragraph">
          <Pilcrow size={16} />
        </Button>
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} title="H1">
          <Heading1 size={16} />
        </Button>
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} title="H2">
          <Heading2 size={16} />
        </Button>
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} title="H3">
          <Heading3 size={16} />
        </Button>
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().toggleBulletList().run()} title="Bullet list">
          <List size={16} />
        </Button>
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().toggleOrderedList().run()} title="Ordered list">
          <ListOrdered size={16} />
        </Button>
        <Button type="button" variant="outline" size="icon" onClick={() => editor.chain().focus().toggleBlockquote().run()} title="Quote">
          <Quote size={16} />
        </Button>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => {
            const href = window.prompt("URL");
            if (href) editor.chain().focus().setLink({ href }).run();
          }}
          title="Link"
        >
          <LinkIcon size={16} />
        </Button>
        <Input
          className="h-10 w-14 p-1"
          type="color"
          title="Text color"
          onChange={(event) => editor.chain().focus().setColor(event.target.value).run()}
        />
        <label className="inline-flex h-10 cursor-pointer items-center justify-center rounded-md border border-input px-3 text-sm">
          <ImageIcon size={16} />
          <input className="hidden" type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => void addImage(event.target.files?.[0])} />
        </label>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
