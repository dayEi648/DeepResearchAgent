/**
 * Markdown 渲染工具
 *
 * 作用：封装 marked + highlight.js，将 Markdown 字符串转为 HTML。
 */

import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

// 配置 marked：代码块高亮
marked.setOptions({
  gfm: true,
  breaks: true,
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
})

/**
 * 将 Markdown 文本渲染为 HTML 字符串
 * @param {string} markdown
 * @returns {string} HTML
 */
export function renderMarkdown(markdown) {
  if (!markdown) return ''
  return marked.parse(markdown)
}

/**
 * 从 Markdown 中提取目录结构（H1 ~ H3）
 * @param {string} markdown
 * @returns {Array<{level:number, text:string, id:string}>}
 */
export function extractToc(markdown) {
  if (!markdown) return []
  const lines = markdown.split('\n')
  const toc = []
  lines.forEach((line) => {
    const match = line.match(/^(#{1,3})\s+(.+)$/)
    if (match) {
      const level = match[1].length
      const text = match[2].trim()
      const id = text.toLowerCase().replace(/[^\w\u4e00-\u9fa5]+/g, '-')
      toc.push({ level, text, id })
    }
  })
  return toc
}
