export function safeFileName(value:string){
    return value.replace(/[\\/:*?"<>|]/g, "_")
}


export function downloadWorkbook(data:BlobPart, fileName:string){
    const url=URL.createObjectURL(new Blob(
        [data],
        {type:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    ))
    const link=document.createElement("a")
    link.href=url
    link.download=safeFileName(fileName)
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
}
