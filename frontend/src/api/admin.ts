import request from "./request"



/**
 * 获取课程列表
 */
export function getCourses(){

    return request.get(
        "/admin/course/list"
    )

}



export function getAdminCourses(
    keyword=""
){

    return request.get(
        "/admin/courses",
        {
            params:{keyword:keyword || undefined}
        }
    )

}



/**
 * 创建课程
 */
export function createCourse(
    data:any
){

    return request.post(
        "/admin/course/create",
        data
    )

}



/**
 * 修改课程
 */
export function updateCourse(
    id:number,
    data:any
){

    return request.put(

        `/admin/course/${id}`,

        data

    )

}



/**
 * 删除课程
 */
export function deleteCourse(
    id:number
){

    return request.delete(

        `/admin/course/${id}`

    )

}


/**
 * 查看课程报名学生
 */
export function getCourseStudents(
    courseId:number
){

    return request.get(
        `/admin/course/${courseId}/students`
    )

}



/**
 * 管理员添加学生
 */
export function addStudent(
    courseId:number,
    studentId:number,
    allowOverCapacity=false
){

    return request.post(

        `/admin/course/${courseId}/add_student`,

        null,

        {
            params:{
                student_id:studentId,
                allow_over_capacity:allowOverCapacity
            }
        }

    )

}



/**
 * 管理员删除学生
 */
export function removeStudent(
    courseId:number,
    studentId:number
){

    return request.delete(

        `/admin/course/${courseId}/remove_student`,

        {

            params:{
                student_id:studentId
            }

        }

    )

}

/**
 * 获取学生列表
 */
export function getStudents(
    keyword=""
){

    return request.get(
        "/admin/students",
        {
            params:{keyword:keyword || undefined}
        }
    )

}



/**
 * 创建学生
 */
export function createStudent(
    data:any
){

    return request.post(
        "/admin/student/create",
        data
    )

}



/**
 * 创建选课阶段
 */
export function createPeriod(
    data:any
){

    return request.post(
        "/admin/period/create",
        data
    )

}


export function updateStudent(
    studentId:number,
    data:{student_no:string, name:string, weight:number}
){

    return request.put(
        `/admin/student/${studentId}`,
        data
    )

}


export function getStudentsPage(
    keyword="",
    page=1,
    pageSize=20
){

    return request.get(
        "/admin/students/page",
        {params:{keyword:keyword || undefined, page, page_size:pageSize}}
    )

}


export function bulkDeleteStudents(data:BulkDeletePayload){
    return request.post("/admin/students/bulk-delete", data)
}


export function getAvailableStudents(
    keyword="",
    limit=50
){

    return request.get(
        "/admin/students/available",
        {params:{keyword:keyword || undefined, limit}}
    )

}


export function getAdminCoursesPage(
    keyword="",
    page=1,
    pageSize=20
){

    return request.get(
        "/admin/courses/page",
        {params:{keyword:keyword || undefined, page, page_size:pageSize}}
    )

}


export interface BulkDeletePayload{
    ids:number[]
    select_all:boolean
    keyword?:string
    excluded_ids:number[]
}


export function bulkDeleteCourses(data:BulkDeletePayload){
    return request.post("/admin/courses/bulk-delete", data)
}


export function getUnassignedCourses(
    keyword="",
    limit=100
){

    return request.get(
        "/admin/courses/unassigned",
        {params:{keyword:keyword || undefined, limit}}
    )

}


export function resetStudentPassword(
    studentId:number,
    newPassword:string
){

    return request.put(
        `/admin/student/${studentId}/password`,
        {new_password:newPassword}
    )

}


export function downloadStudentImportTemplate(){

    return request.get(
        "/admin/students/import-template",
        {responseType:"blob"}
    )

}


export function importStudents(file:File){

    const formData=new FormData()
    formData.append("file", file)

    return request.post(
        "/admin/students/import",
        formData,
        {
            headers:{"Content-Type":"multipart/form-data"}
        }
    )

}


export function updatePeriod(
    periodId:number,
    data:any
){

    return request.put(
        `/admin/period/${periodId}`,
        data
    )

}



export function getPeriods(){

    return request.get(
        "/admin/periods"
    )

}


export function getPeriodDetail(
    periodId:number
){

    return request.get(
        `/admin/period/${periodId}`
    )

}


export function exportPeriodSelections(
    periodId:number
){

    return request.get(
        `/admin/period/${periodId}/export`,
        {responseType:"blob", timeout:30000}
    )

}


export function exportCourseSelections(
    courseId:number
){

    return request.get(
        `/admin/course/${courseId}/students/export`,
        {responseType:"blob", timeout:30000}
    )

}


export function addPeriodCourses(
    periodId:number,
    courseIds:number[]
){

    return request.post(
        `/admin/period/${periodId}/courses`,
        {course_ids:courseIds}
    )

}


export function removePeriodCourse(
    periodId:number,
    courseId:number
){

    return request.delete(
        `/admin/period/${periodId}/courses/${courseId}`
    )

}


export function updateCourseStatus(
    courseId:number,
    status:"OPEN" | "CLOSED"
){

    return request.put(
        `/admin/course/${courseId}/status`,
        {status}
    )

}



/**
 * 结算选课阶段
 */
export function finalizePeriod(
    periodId:number
){

    return request.post(

        "/admin/period/finalize",

        null,

        {
            params:{
                period_id:periodId
            }
        }

    )

}
