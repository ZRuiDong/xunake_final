<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { downloadWorkbook } from "../../utils/download"

import {
    addPeriodCourses,
    addStudent,
    exportCourseSelections,
    exportPeriodSelections,
    getAvailableStudents,
    getCourseStudents,
    getPeriodDetail,
    getUnassignedCourses,
    removePeriodCourse,
    removeStudent
} from "../../api/admin"

interface PeriodInfo {
    id:number
    name:string
    start_time:string
    end_time:string
    status:string
    course_count:number
}

interface CourseInfo {
    id:number
    name:string
    description:string | null
    instructor:string | null
    location:string | null
    schedule:string | null
    capacity:number
    selected_count:number
    total_count:number
    over_capacity:boolean
}

interface StudentOption {
    id:number
    student_no:string
    name:string
}

interface SelectionStudent {
    student_id:number
    student_no:string
    name:string
    status:string
    rank:number | null
}

const route=useRoute()
const router=useRouter()
const periodId=Number(route.params.id)
const period=ref<PeriodInfo | null>(null)
const courses=ref<CourseInfo[]>([])
const unassignedCourses=ref<Array<{id:number, name:string}>>([])
const studentOptions=ref<StudentOption[]>([])
const studentSearching=ref(false)
const studentVisible=ref(false)
const currentCourse=ref<CourseInfo | null>(null)
const selectedStudents=ref<SelectionStudent[]>([])
const addStudentId=ref<number>()
const loading=ref(false)
const exportingPeriod=ref(false)
const exportingCourse=ref(false)
const courseDialogVisible=ref(false)
const courseIds=ref<number[]>([])
const managementRuleText=computed(()=>{
    if(period.value?.status==="WAITING"){
        return "未开始：可添加或移出课程，可调整课程容量，也可增删学生。"
    }
    if(period.value?.status==="ACTIVE"){
        return "进行中：可新增课程、调整容量和增删学生；录取按报名先后顺序处理，已有报名的课程不可移出阶段。"
    }
    return "已结束：课程与容量冻结；管理员仍可修正最终名单，移除学生不会自动递补，未录取学生可手动录取。"
})

function formatDateTime(value:string){
    return value.replace("T", " ").split(".")[0].slice(0, 19)
}

function periodStatusLabel(status:string){
    const labels:Record<string, string>={
        WAITING:"未开始",
        ACTIVE:"进行中",
        CLOSED:"已结束"
    }
    return labels[status] || status
}

function selectionStatusLabel(status:string){
    const labels:Record<string, string>={
        WAITING:"候补中",
        SELECTED:"容量内",
        FINAL:"已确认",
        REJECTED:"未录取"
    }
    return labels[status] || status
}

function statusType(status:string){
    if(status==="ACTIVE" || status==="FINAL") return "success"
    if(status==="WAITING") return "warning"
    if(status==="REJECTED") return "danger"
    return "info"
}

async function handleExportPeriod(){
    if(!period.value) return
    exportingPeriod.value=true
    try{
        const response=await exportPeriodSelections(periodId)
        downloadWorkbook(response.data, `${period.value.name}_选课情况.xlsx`)
        ElMessage.success("阶段选课情况已导出")
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "导出阶段选课情况失败")
    }finally{
        exportingPeriod.value=false
    }
}

async function handleExportCourse(){
    if(!currentCourse.value) return
    exportingCourse.value=true
    try{
        const response=await exportCourseSelections(currentCourse.value.id)
        downloadWorkbook(response.data, `${currentCourse.value.name}_选课情况.xlsx`)
        ElMessage.success("课程选课情况已导出")
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "导出课程选课情况失败")
    }finally{
        exportingCourse.value=false
    }
}

async function loadDetail(){
    if(!Number.isInteger(periodId)){
        ElMessage.error("轮次ID无效")
        router.replace("/admin/period")
        return
    }
    loading.value=true
    try{
        const detailRes=await getPeriodDetail(periodId)
        period.value=detailRes.data.period
        courses.value=detailRes.data.courses
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "获取轮次详情失败")
    }finally{
        loading.value=false
    }
}

async function openAddCourses(){
    try{
        const response=await getUnassignedCourses()
        unassignedCourses.value=response.data
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "获取待选课程失败")
        return
    }
    if(unassignedCourses.value.length===0){
        ElMessage.warning("没有尚未进入轮次的课程")
        return
    }
    courseIds.value=[]
    courseDialogVisible.value=true
}

async function searchStudentOptions(keyword:string){
    studentSearching.value=true
    try{
        const response=await getAvailableStudents(keyword)
        const displayedIds=new Set(selectedStudents.value.map(student=>student.student_id))
        studentOptions.value=response.data.filter(
            (student:StudentOption)=>!displayedIds.has(student.id)
        )
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "搜索学生失败")
    }finally{
        studentSearching.value=false
    }
}

async function handleAddCourses(){
    if(courseIds.value.length===0){
        ElMessage.warning("请至少选择一门课程")
        return
    }
    try{
        await addPeriodCourses(periodId, courseIds.value)
        ElMessage.success("课程已加入本轮次")
        courseDialogVisible.value=false
        await loadDetail()
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "添加课程失败")
    }
}

async function handleRemoveCourse(course:CourseInfo){
    try{
        await ElMessageBox.confirm(
            `确认将“${course.name}”移出当前选课阶段吗？课程会返回课程库。`,
            "移出课程",
            {type:"warning"}
        )
        await removePeriodCourse(periodId, course.id)
        ElMessage.success("课程已移出阶段")
        await loadDetail()
    }catch(error:any){
        if(error!=="cancel"){
            ElMessage.error(error.response?.data?.detail || "移出课程失败")
        }
    }
}

async function showStudents(course:CourseInfo){
    currentCourse.value=course
    addStudentId.value=undefined
    try{
        const res=await getCourseStudents(course.id)
        selectedStudents.value=res.data.students
        currentCourse.value={
            ...course,
            selected_count:res.data.selected_count,
            over_capacity:res.data.over_capacity
        }
        await searchStudentOptions("")
        studentVisible.value=true
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "获取课程选课情况失败")
    }
}

async function addSelectedStudent(force=false){
    if(!currentCourse.value || !addStudentId.value) return
    await addStudent(currentCourse.value.id, addStudentId.value, force)
    ElMessage.success("学生已添加到课程")
    await loadDetail()
    const refreshed=courses.value.find(item=>item.id===currentCourse.value?.id)
    if(refreshed) await showStudents(refreshed)
}

async function handleAddStudent(){
    if(!addStudentId.value){
        ElMessage.warning("请选择要添加的学生")
        return
    }

    try{
        await addSelectedStudent(false)
    }catch(error:any){
        const detail=error.response?.data?.detail
        if(error.response?.status===409 && detail?.code==="COURSE_CAPACITY_EXCEEDED"){
            try{
                await ElMessageBox.confirm(
                    `课程容量为 ${detail.capacity} 人，当前已确认 ${detail.selected_count} 人。继续添加将超出容量，仍要添加吗？`,
                    "超出课程容量",
                    {type:"warning", confirmButtonText:"仍然添加", cancelButtonText:"取消"}
                )
                await addSelectedStudent(true)
            }catch(confirmError:any){
                if(confirmError!=="cancel"){
                    ElMessage.error(confirmError.response?.data?.detail || "添加学生失败")
                }
            }
            return
        }
        ElMessage.error(typeof detail==="string" ? detail : "添加学生失败")
    }
}

async function handleRemoveStudent(student:SelectionStudent){
    if(!currentCourse.value) return
    try{
        await ElMessageBox.confirm(
            `确认从“${currentCourse.value.name}”移除 ${student.name} 吗？`,
            "移除学生",
            {type:"warning"}
        )
        await removeStudent(currentCourse.value.id, student.student_id)
        ElMessage.success("学生已移除")
        await loadDetail()
        const refreshed=courses.value.find(item=>item.id===currentCourse.value?.id)
        if(refreshed) await showStudents(refreshed)
    }catch(error:any){
        if(error!=="cancel"){
            ElMessage.error(error.response?.data?.detail || "移除学生失败")
        }
    }
}

async function handleAdmitRejected(student:SelectionStudent){
    addStudentId.value=student.student_id
    await handleAddStudent()
}

onMounted(loadDetail)
</script>

<template>
<section v-loading="loading">
    <el-button link type="primary" class="back-button" @click="router.push('/admin/period')">
        ← 返回轮次列表
    </el-button>

    <template v-if="period">
        <div class="page-heading">
            <div>
                <div class="title-row">
                    <h1>{{period.name}}</h1>
                    <el-tag :type="statusType(period.status)">{{periodStatusLabel(period.status)}}</el-tag>
                </div>
                <p>{{formatDateTime(period.start_time)}} 至 {{formatDateTime(period.end_time)}}</p>
            </div>
            <div class="heading-actions">
                <span class="course-total">{{period.course_count}} 门课程</span>
                <el-button :loading="exportingPeriod" @click="handleExportPeriod">
                    导出选课情况
                </el-button>
                <el-button
                    v-if="period.status!=='CLOSED'"
                    type="primary"
                    @click="openAddCourses"
                >添加课程</el-button>
            </div>
        </div>

        <el-alert
            :title="managementRuleText"
            type="info"
            show-icon
            :closable="false"
            class="rule-alert"
        />

        <el-table :data="courses" border>
            <el-table-column prop="name" label="课程名称" min-width="140" />
            <el-table-column prop="description" label="课程描述" min-width="180" />
            <el-table-column prop="instructor" label="教师" min-width="100" />
            <el-table-column prop="schedule" label="上课时间" min-width="140" />
            <el-table-column prop="location" label="地点" min-width="120" />
            <el-table-column prop="capacity" label="容量" width="80" />
            <el-table-column prop="total_count" label="报名总数" width="100" />
            <el-table-column label="已确认" width="120">
                <template #default="scope">
                    <span :class="{'over-capacity':scope.row.over_capacity}">
                        {{scope.row.selected_count}} / {{scope.row.capacity}}
                    </span>
                    <el-tag v-if="scope.row.over_capacity" type="danger" size="small">超员</el-tag>
                </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
                <template #default="scope">
                    <el-button type="primary" @click="showStudents(scope.row)">选课情况</el-button>
                    <el-button
                        v-if="period?.status==='WAITING'"
                        type="danger"
                        link
                        @click="handleRemoveCourse(scope.row)"
                    >移出</el-button>
                </template>
            </el-table-column>
        </el-table>
    </template>

    <el-dialog v-model="courseDialogVisible" title="添加未分配课程" width="520px">
        <el-select
            v-model="courseIds"
            multiple
            filterable
            placeholder="选择课程"
            style="width:100%"
        >
            <el-option
                v-for="course in unassignedCourses"
                :key="course.id"
                :label="course.name"
                :value="course.id"
            />
        </el-select>
        <template #footer>
            <el-button @click="courseDialogVisible=false">取消</el-button>
            <el-button type="primary" @click="handleAddCourses">确认添加</el-button>
        </template>
    </el-dialog>

    <el-dialog
        v-model="studentVisible"
        :title="`${currentCourse?.name || ''} · 选课情况`"
        width="780px"
    >
        <el-alert
            v-if="currentCourse?.over_capacity"
            title="当前课程人数已超出课程容量"
            type="warning"
            show-icon
            :closable="false"
            class="capacity-alert"
        />
        <div class="add-row">
            <el-select
                v-model="addStudentId"
                filterable
                remote
                :remote-method="searchStudentOptions"
                :loading="studentSearching"
                placeholder="按学号或姓名选择学生"
                style="width:300px"
            >
                <el-option
                    v-for="student in studentOptions"
                    :key="student.id"
                    :label="`${student.student_no} · ${student.name}`"
                    :value="student.id"
                />
            </el-select>
            <el-button type="primary" @click="handleAddStudent">添加学生</el-button>
            <el-button
                class="export-button"
                :loading="exportingCourse"
                @click="handleExportCourse"
            >导出本课程</el-button>
        </div>

        <el-table :data="selectedStudents" border>
            <el-table-column label="排名" width="70">
                <template #default="scope">{{scope.row.rank ?? "-"}}</template>
            </el-table-column>
            <el-table-column prop="student_no" label="学号" min-width="120" />
            <el-table-column prop="name" label="姓名" min-width="100" />
            <el-table-column label="状态" width="100">
                <template #default="scope">
                    <el-tag :type="statusType(scope.row.status)">{{selectionStatusLabel(scope.row.status)}}</el-tag>
                </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
                <template #default="scope">
                    <el-button
                        v-if="scope.row.status==='REJECTED'"
                        type="success"
                        link
                        @click="handleAdmitRejected(scope.row)"
                    >录取</el-button>
                    <el-button type="danger" link @click="handleRemoveStudent(scope.row)">移除</el-button>
                </template>
            </el-table-column>
        </el-table>
    </el-dialog>
</section>
</template>

<style scoped>
.back-button{margin-bottom:18px}
.page-heading{display:flex; justify-content:space-between; gap:24px; align-items:center; margin-bottom:24px}
.page-heading h1{margin:0}
.page-heading p{margin-top:8px; color:#6b7a89}
.title-row{display:flex; align-items:center; gap:12px}
.course-total{padding:8px 14px; border-radius:999px; background:#e3efed; color:#17635e; font-weight:700}
.heading-actions{display:flex; align-items:center; gap:12px}
.over-capacity{color:#c0392b; font-weight:700; margin-right:6px}
.capacity-alert{margin-bottom:16px}
.rule-alert{margin-bottom:16px}
.add-row{display:flex; gap:10px; margin-bottom:18px}
.export-button{margin-left:auto}
@media (max-width:700px){.page-heading{align-items:flex-start; flex-direction:column}.add-row{align-items:stretch; flex-direction:column}}
</style>
