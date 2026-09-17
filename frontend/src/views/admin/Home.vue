<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"

import {
    bulkDeleteCourses,
    createCourse,
    getAdminCoursesPage,
    updateCourseStatus,
    updateCourse,
    type BulkDeletePayload
} from "../../api/admin"

interface Course {
    id:number
    name:string
    description:string | null
    instructor:string | null
    location:string | null
    schedule:string | null
    capacity:number
    status:string
    selected_count:number
    period_id:number | null
    period_name:string | null
    period_status:string | null
}

const courses=ref<Course[]>([])
const keyword=ref("")
const appliedKeyword=ref("")
const page=ref(1)
const pageSize=ref(20)
const total=ref(0)
const loading=ref(false)

const tableRef=ref<any>()
const syncingSelection=ref(false)
const selectAllMatching=ref(false)
const selectedIds=ref<Set<number>>(new Set())
const excludedIds=ref<Set<number>>(new Set())
const selectedCount=computed(()=>selectAllMatching.value
    ? Math.max(total.value-excludedIds.value.size, 0)
    : selectedIds.value.size
)

const dialogVisible=ref(false)
const editMode=ref(false)
const saving=ref(false)
const form=ref({
    id:0,
    name:"",
    description:"",
    instructor:"",
    location:"",
    schedule:"",
    capacity:20
})

function formatPeriodStatus(status:string | null){
    const labels:Record<string, string>={
        WAITING:"未开始",
        ACTIVE:"进行中",
        CLOSED:"已结束"
    }
    return status ? labels[status] || status : "未进入轮次"
}

function periodTagType(status:string | null){
    if(status==="ACTIVE") return "success"
    if(status==="WAITING") return "warning"
    return "info"
}

async function syncCurrentPageSelection(){
    await nextTick()
    if(!tableRef.value) return
    syncingSelection.value=true
    tableRef.value.clearSelection()
    for(const course of courses.value){
        const selected=selectAllMatching.value
            ? !excludedIds.value.has(course.id)
            : selectedIds.value.has(course.id)
        if(selected) tableRef.value.toggleRowSelection(course, true)
    }
    await nextTick()
    syncingSelection.value=false
}

async function loadCourses(){
    loading.value=true
    try{
        const response=await getAdminCoursesPage(
            appliedKeyword.value,
            page.value,
            pageSize.value
        )
        courses.value=response.data.items
        total.value=response.data.total

        const lastPage=Math.max(Math.ceil(total.value/pageSize.value), 1)
        if(page.value>lastPage){
            page.value=lastPage
            await loadCourses()
            return
        }
        await syncCurrentPageSelection()
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "获取课程失败")
    }finally{
        loading.value=false
    }
}

function clearSelection(){
    selectAllMatching.value=false
    selectedIds.value=new Set()
    excludedIds.value=new Set()
    tableRef.value?.clearSelection()
}

async function searchCourses(){
    appliedKeyword.value=keyword.value.trim()
    page.value=1
    clearSelection()
    await loadCourses()
}

function handleSelectionChange(selection:Course[]){
    if(syncingSelection.value) return
    const pageIds=new Set(courses.value.map(course=>course.id))
    const selectedPageIds=new Set(selection.map(course=>course.id))

    if(selectAllMatching.value){
        const nextExcluded=new Set(excludedIds.value)
        for(const id of pageIds){
            if(selectedPageIds.has(id)) nextExcluded.delete(id)
            else nextExcluded.add(id)
        }
        excludedIds.value=nextExcluded
    }else{
        const nextSelected=new Set(selectedIds.value)
        for(const id of pageIds) nextSelected.delete(id)
        for(const id of selectedPageIds) nextSelected.add(id)
        selectedIds.value=nextSelected
    }
}

async function handleSelectAllMatching(value:boolean){
    selectedIds.value=new Set()
    excludedIds.value=new Set()
    selectAllMatching.value=value
    await syncCurrentPageSelection()
}

function onSelectAllChange(value:string | number | boolean){
    handleSelectAllMatching(Boolean(value))
}

function changePage(value:number){
    page.value=value
    loadCourses()
}

function changePageSize(value:number){
    pageSize.value=value
    page.value=1
    loadCourses()
}

function selectionPayload(ids?:number[]):BulkDeletePayload{
    if(ids) return {ids, select_all:false, excluded_ids:[]}
    return {
        ids:Array.from(selectedIds.value),
        select_all:selectAllMatching.value,
        keyword:appliedKeyword.value || undefined,
        excluded_ids:Array.from(excludedIds.value)
    }
}

async function confirmDelete(payload:BulkDeletePayload, count:number){
    if(count===0){
        ElMessage.warning("请先选择要删除的课程")
        return
    }
    try{
        await ElMessageBox.confirm(
            `确认删除 ${count} 门课程吗？课程的选课记录会同步删除，已进入轮次的课程也会从对应轮次移除，操作无法撤销。`,
            "批量删除课程",
            {type:"warning", confirmButtonText:"确认删除", cancelButtonText:"取消"}
        )
        const response=await bulkDeleteCourses(payload)
        ElMessage.success(
            `已删除 ${response.data.deleted_count} 门课程，并清理 ${response.data.selection_deleted_count} 条选课记录`
        )
        clearSelection()
        await loadCourses()
    }catch(error:any){
        if(error!=="cancel"){
            ElMessage.error(error.response?.data?.detail || "删除课程失败")
        }
    }
}

function deleteSelected(){
    confirmDelete(selectionPayload(), selectedCount.value)
}

function deleteCourse(course:Course){
    confirmDelete(selectionPayload([course.id]), 1)
}

function openCreate(){
    editMode.value=false
    form.value={
        id:0,
        name:"",
        description:"",
        instructor:"",
        location:"",
        schedule:"",
        capacity:20
    }
    dialogVisible.value=true
}

function openEdit(course:Course){
    editMode.value=true
    form.value={
        id:course.id,
        name:course.name,
        description:course.description || "",
        instructor:course.instructor || "",
        location:course.location || "",
        schedule:course.schedule || "",
        capacity:course.capacity
    }
    dialogVisible.value=true
}

async function saveCourse(){
    if(!form.value.name.trim()){
        ElMessage.warning("请输入课程名称")
        return
    }
    saving.value=true
    try{
        const data={
            name:form.value.name.trim(),
            description:form.value.description.trim() || null,
            instructor:form.value.instructor.trim() || null,
            location:form.value.location.trim() || null,
            schedule:form.value.schedule.trim() || null,
            capacity:form.value.capacity
        }
        if(editMode.value) await updateCourse(form.value.id, data)
        else await createCourse(data)

        ElMessage.success("保存成功")
        dialogVisible.value=false
        await loadCourses()
    }catch(error:any){
        ElMessage.error(error.response?.data?.detail || "保存失败")
    }finally{
        saving.value=false
    }
}

async function toggleCourseStatus(course:Course){
    const nextStatus=course.status==="OPEN" ? "CLOSED" : "OPEN"
    const action=nextStatus==="OPEN" ? "开放" : "暂停"
    try{
        await ElMessageBox.confirm(
            `确认${action}课程“${course.name}”吗？${nextStatus==="CLOSED" ? "暂停后学生不能继续选择该课程，已有记录会保留。" : ""}`,
            `${action}课程`,
            {type:nextStatus==="CLOSED" ? "warning" : "info"}
        )
        await updateCourseStatus(course.id, nextStatus)
        ElMessage.success(`课程已${action}`)
        await loadCourses()
    }catch(error:any){
        if(error!=="cancel"){
            ElMessage.error(error.response?.data?.detail || `${action}课程失败`)
        }
    }
}

onMounted(loadCourses)
</script>

<template>
<section>
    <div class="page-heading">
        <div>
            <h1>课程库</h1>
            <p>分页管理课程，可按课程名称搜索并批量操作。</p>
        </div>
        <div class="heading-actions">
            <el-input
                v-model="keyword"
                clearable
                placeholder="按课程名称搜索"
                class="search-input"
                @keyup.enter="searchCourses"
                @clear="searchCourses"
            />
            <el-button @click="searchCourses">搜索</el-button>
            <el-button type="primary" @click="openCreate">新增课程</el-button>
        </div>
    </div>

    <div class="selection-toolbar">
        <el-checkbox
            :model-value="selectAllMatching"
            :disabled="total===0"
            @change="onSelectAllChange"
        >全选当前搜索结果（{{total}} 条）</el-checkbox>
        <span>已选择 {{selectedCount}} 条</span>
        <el-button type="danger" :disabled="selectedCount===0" @click="deleteSelected">
            批量删除
        </el-button>
    </div>

    <el-table
        ref="tableRef"
        v-loading="loading"
        :data="courses"
        row-key="id"
        border
        @selection-change="handleSelectionChange"
    >
        <el-table-column type="selection" width="48" reserve-selection />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="课程名称" min-width="130" />
        <el-table-column prop="description" label="课程描述" min-width="180" />
        <el-table-column prop="instructor" label="教师" min-width="100" />
        <el-table-column prop="schedule" label="上课时间" min-width="140" />
        <el-table-column prop="location" label="地点" min-width="120" />
        <el-table-column prop="capacity" label="容量" width="80" />
        <el-table-column prop="selected_count" label="已确认" width="90" />
        <el-table-column label="课程状态" width="95">
            <template #default="scope">
                <el-tag :type="scope.row.status==='OPEN' ? 'success' : 'info'">
                    {{scope.row.status==='OPEN' ? '开放' : '暂停'}}
                </el-tag>
            </template>
        </el-table-column>
        <el-table-column label="选课轮次" min-width="170">
            <template #default="scope">
                <div v-if="scope.row.period_id" class="period-cell">
                    <span>{{scope.row.period_name}}</span>
                    <el-tag :type="periodTagType(scope.row.period_status)" size="small">
                        {{formatPeriodStatus(scope.row.period_status)}}
                    </el-tag>
                </div>
                <el-tag v-else type="info">未进入轮次</el-tag>
            </template>
        </el-table-column>
        <el-table-column label="操作" width="185" fixed="right">
            <template #default="scope">
                <el-button link @click="openEdit(scope.row)">修改</el-button>
                <el-button
                    :type="scope.row.status==='OPEN' ? 'warning' : 'success'"
                    link
                    @click="toggleCourseStatus(scope.row)"
                >{{scope.row.status==='OPEN' ? '暂停' : '开放'}}</el-button>
                <el-button type="danger" link @click="deleteCourse(scope.row)">删除</el-button>
            </template>
        </el-table-column>
    </el-table>

    <div class="pagination-row">
        <el-pagination
            background
            layout="total, sizes, prev, pager, next, jumper"
            :total="total"
            :current-page="page"
            :page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="changePage"
            @size-change="changePageSize"
        />
    </div>

    <el-dialog v-model="dialogVisible" :title="editMode ? '修改课程' : '新增课程'" width="500px">
        <el-form label-width="90px">
            <el-form-item label="课程名称" required>
                <el-input v-model="form.name" maxlength="100" />
            </el-form-item>
            <el-form-item label="课程描述">
                <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" />
            </el-form-item>
            <el-form-item label="授课教师">
                <el-input v-model="form.instructor" maxlength="100" />
            </el-form-item>
            <el-form-item label="上课时间">
                <el-input v-model="form.schedule" maxlength="200" placeholder="例如：每周三 16:00-17:30" />
            </el-form-item>
            <el-form-item label="上课地点">
                <el-input v-model="form.location" maxlength="200" />
            </el-form-item>
            <el-form-item label="课程容量" required>
                <el-input-number v-model="form.capacity" :min="1" />
            </el-form-item>
        </el-form>
        <template #footer>
            <el-button @click="dialogVisible=false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="saveCourse">保存</el-button>
        </template>
    </el-dialog>
</section>
</template>

<style scoped>
.page-heading{display:flex; align-items:flex-start; justify-content:space-between; gap:24px; margin-bottom:20px}
.page-heading h1{margin-bottom:8px}
.page-heading p{color:#6b7a89}
.heading-actions{display:flex; align-items:center; gap:8px}
.search-input{width:230px}
.selection-toolbar{display:flex; align-items:center; gap:18px; margin-bottom:14px; padding:12px 16px; border:1px solid #dce5e5; border-radius:10px; background:#fff}
.selection-toolbar span{color:#6b7a89}
.selection-toolbar .el-button{margin-left:auto}
.period-cell{display:flex; align-items:center; gap:8px; flex-wrap:wrap}
.pagination-row{display:flex; justify-content:flex-end; margin-top:18px}
@media (max-width:800px){
    .page-heading{align-items:stretch; flex-direction:column}
    .heading-actions{align-items:stretch; flex-direction:column}
    .search-input{width:100%}
    .selection-toolbar{align-items:flex-start; flex-direction:column; gap:8px}
    .selection-toolbar .el-button{margin-left:0}
    .pagination-row{justify-content:flex-start; overflow:auto}
}
</style>
