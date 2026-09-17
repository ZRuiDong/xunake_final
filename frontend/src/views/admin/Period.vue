<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { downloadWorkbook } from "../../utils/download"

import {
    createPeriod,
    exportPeriodSelections,
    finalizePeriod,
    getAdminCourses,
    getPeriods,
    updatePeriod
} from "../../api/admin"

interface Period {
    id:number
    name:string
    start_time:string
    end_time:string
    status:"WAITING" | "ACTIVE" | "CLOSED"
    finalized_time:string | null
    course_count:number
}

interface CourseOption {
    id:number
    name:string
    period_id:number | null
}

const router=useRouter()
const periods=ref<Period[]>([])
const courses=ref<CourseOption[]>([])
const dialogVisible=ref(false)
const editMode=ref(false)
const saving=ref(false)
const exportingPeriodId=ref<number | null>(null)
const form=ref({
    id:0,
    name:"",
    start_time:"",
    end_time:"",
    course_ids:[] as number[]
})

const availableCourses=computed(()=>courses.value.filter(course=>course.period_id===null))
const hasOpenPeriod=computed(()=>periods.value.some(
    period=>period.status==="WAITING" || period.status==="ACTIVE"
))

function formatDateTime(value:string | null){
    if(!value) return "-"
    return value.replace("T", " ").split(".")[0].slice(0, 19)
}

function inputDateTime(value:string){
    return formatDateTime(value)==="-" ? "" : formatDateTime(value)
}

function statusLabel(status:string){
    return {WAITING:"未开始", ACTIVE:"进行中", CLOSED:"已结束"}[status] || status
}

function statusType(status:string){
    if(status==="ACTIVE") return "success"
    if(status==="WAITING") return "warning"
    return "info"
}

async function loadData(){
    try{
        const [periodRes, courseRes]=await Promise.all([
            getPeriods(),
            getAdminCourses()
        ])
        periods.value=periodRes.data
        courses.value=courseRes.data
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "获取轮次信息失败")
    }
}

function openCreate(){
    if(hasOpenPeriod.value){
        ElMessage.warning("当前已有未结束的选课轮次")
        return
    }
    if(availableCourses.value.length===0){
        ElMessage.warning("课程库中没有尚未进入轮次的课程")
        return
    }
    editMode.value=false
    form.value={id:0, name:"", start_time:"", end_time:"", course_ids:[]}
    dialogVisible.value=true
}

function openEdit(period:Period){
    editMode.value=true
    form.value={
        id:period.id,
        name:period.name,
        start_time:inputDateTime(period.start_time),
        end_time:inputDateTime(period.end_time),
        course_ids:[]
    }
    dialogVisible.value=true
}

async function save(){
    if(!form.value.name.trim() || !form.value.start_time || !form.value.end_time){
        ElMessage.warning("请完整填写轮次名称和时间")
        return
    }
    if(!editMode.value && form.value.course_ids.length===0){
        ElMessage.warning("请至少选择一门课程")
        return
    }

    saving.value=true
    try{
        const data={
            name:form.value.name.trim(),
            start_time:form.value.start_time,
            end_time:form.value.end_time
        }
        if(editMode.value){
            await updatePeriod(form.value.id, data)
        }else{
            await createPeriod({...data, course_ids:form.value.course_ids})
        }
        ElMessage.success(editMode.value ? "轮次时间已更新" : "选课轮次创建成功")
        dialogVisible.value=false
        await loadData()
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "保存失败")
    }finally{
        saving.value=false
    }
}

async function closePeriod(period:Period){
    try{
        await ElMessageBox.confirm(
            `确认提前结束“${period.name}”吗？容量内的学生将被最终确认。`,
            "结束选课轮次",
            {type:"warning"}
        )
        await finalizePeriod(period.id)
        ElMessage.success("轮次已结束")
        await loadData()
    }catch(error:any){
        if(error!=="cancel"){
            ElMessage.error(error.response?.data?.detail || "结束轮次失败")
        }
    }
}

function showDetail(period:Period){
    router.push(`/admin/period/${period.id}`)
}

async function exportPeriod(period:Period){
    exportingPeriodId.value=period.id
    try{
        const response=await exportPeriodSelections(period.id)
        downloadWorkbook(response.data, `${period.name}_选课情况.xlsx`)
        ElMessage.success("阶段选课情况已导出")
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "导出阶段选课情况失败")
    }finally{
        exportingPeriodId.value=null
    }
}

onMounted(loadData)
</script>

<template>
<section>
    <div class="page-heading">
        <div>
            <h1>选课轮次管理</h1>
            <p>每次从课程库选择尚未进入轮次的课程。系统同一时间只允许一个未结束轮次。</p>
        </div>
        <el-button type="primary" :disabled="hasOpenPeriod" @click="openCreate">
            新建选课轮次
        </el-button>
    </div>

    <el-alert
        v-if="hasOpenPeriod"
        title="当前轮次结束后，才能创建下一轮次"
        type="info"
        show-icon
        :closable="false"
        class="notice"
    />

    <el-table :data="periods" border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="轮次名称" min-width="140" />
        <el-table-column prop="course_count" label="课程数" width="90" />
        <el-table-column label="开始时间" min-width="170">
            <template #default="scope">{{formatDateTime(scope.row.start_time)}}</template>
        </el-table-column>
        <el-table-column label="结束时间" min-width="170">
            <template #default="scope">{{formatDateTime(scope.row.end_time)}}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
            <template #default="scope">
                <el-tag :type="statusType(scope.row.status)">{{statusLabel(scope.row.status)}}</el-tag>
            </template>
        </el-table-column>
        <el-table-column label="操作" width="310" fixed="right">
            <template #default="scope">
                <el-button type="primary" link @click="showDetail(scope.row)">选课详情</el-button>
                <el-button
                    type="success"
                    link
                    :loading="exportingPeriodId===scope.row.id"
                    @click="exportPeriod(scope.row)"
                >导出</el-button>
                <el-button type="primary" link @click="openEdit(scope.row)">修改时间</el-button>
                <el-button
                    v-if="scope.row.status!=='CLOSED'"
                    type="danger"
                    link
                    @click="closePeriod(scope.row)"
                >提前结束</el-button>
            </template>
        </el-table-column>
    </el-table>

    <el-dialog
        v-model="dialogVisible"
        :title="editMode ? '修改选课轮次' : '新建选课轮次'"
        width="620px"
    >
        <el-form label-width="100px">
            <el-form-item label="轮次名称" required>
                <el-input v-model="form.name" maxlength="100" />
            </el-form-item>
            <el-form-item label="开始时间" required>
                <el-date-picker
                    v-model="form.start_time"
                    type="datetime"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    format="YYYY-MM-DD HH:mm:ss"
                    placeholder="选择开始时间"
                />
            </el-form-item>
            <el-form-item label="结束时间" required>
                <el-date-picker
                    v-model="form.end_time"
                    type="datetime"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    format="YYYY-MM-DD HH:mm:ss"
                    placeholder="结束时间不能早于当前时间"
                />
            </el-form-item>
            <el-form-item v-if="!editMode" label="本轮课程" required>
                <el-select
                    v-model="form.course_ids"
                    multiple
                    filterable
                    collapse-tags
                    placeholder="选择尚未进入轮次的课程"
                    style="width:100%"
                >
                    <el-option
                        v-for="course in availableCourses"
                        :key="course.id"
                        :label="course.name"
                        :value="course.id"
                    />
                </el-select>
            </el-form-item>
        </el-form>
        <template #footer>
            <el-button @click="dialogVisible=false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </template>
    </el-dialog>
</section>
</template>

<style scoped>
.page-heading{display:flex; justify-content:space-between; align-items:flex-start; gap:24px; margin-bottom:20px}
.page-heading h1{margin-bottom:8px}
.page-heading p{max-width:720px; color:#6b7a89}
.notice{margin-bottom:18px}
@media (max-width:700px){.page-heading{flex-direction:column; align-items:stretch}}
</style>
