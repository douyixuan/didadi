// Download the current Markdown bytes. No backend write or HTML conversion.
export function downloadMarkdown(content,name='demo.md'){
  const url=URL.createObjectURL(new Blob([content],{type:'text/markdown;charset=utf-8'}));
  const link=document.createElement('a');link.href=url;link.download=name;
  document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
