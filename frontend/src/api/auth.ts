import request from "./request"


export function changePassword(data:{
    old_password:string
    new_password:string
}){
    return request.post("/auth/change-password", data)
}
