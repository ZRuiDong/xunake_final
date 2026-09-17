import request from "./request"


export function getProfile(){

    return request.get(
        "/student/profile"
    )

}



export function getCourses(){

    return request.get(
        "/student/courses"
    )

}



export function selectCourse(
    courseId:number
){

    return request.post(
        `/student/select/${courseId}`
    )

}



export function getRank(
    courseId:number
){

    return request.get(
        `/student/course/${courseId}/rank`
    )

}



export function cancelCourse(
    courseId:number
){

    return request.delete(
        `/student/cancel/${courseId}`
    )

}