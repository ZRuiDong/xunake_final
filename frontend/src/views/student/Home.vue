<script setup lang="ts">

import {
    computed,
    ref,
    onMounted
} from "vue"


import {
    ElMessage
} from "element-plus"


import {
    useRouter
} from "vue-router"

import ChangePasswordDialog from "../../components/ChangePasswordDialog.vue"


const router=useRouter()

const passwordRequired=ref(localStorage.getItem("must_change_password")==="true")

const passwordVisible=ref(passwordRequired.value)


function logout(){

    localStorage.removeItem(
        "token"
    )

    localStorage.removeItem(
        "role"
    )

    localStorage.removeItem(
        "must_change_password"
    )

    router.push(
        "/login"
    )

}


import {

    getCourses,

    getProfile,

    selectCourse,

    getRank,

    cancelCourse

} from "../../api/student"



interface Course{


    id:number

    name:string

    description:string

    instructor:string|null

    location:string|null

    schedule:string|null

    capacity:number

    selected_count:number

    status:string

    period_active:boolean

    can_select:boolean


    is_selected:boolean


    selection_status:string|null

    period_id:number

    period_name:string


}



const courses = ref<Course[]>([])
const pendingCourse = ref<number|null>(null)

interface StudentSelection{
    course_id:number
    course_name:string
    period_id:number | null
    period_name:string | null
    period_status:string | null
    status:string
}

interface StudentProfile{
    name:string
    student_no:string
    selection:StudentSelection | null
    selections:StudentSelection[]
}

const student = ref<StudentProfile>({
    name: "学生",
    student_no: "",
    selection:null,
    selections:[]
})

const currentSelections=computed(()=>(student.value.selections || []).filter(
    selection=>selection.status!=="REJECTED"
))
const finalSelectionCount=computed(()=>currentSelections.value.filter(
    selection=>selection.status==="FINAL"
).length)



const rankVisible = ref(false)



const rankInfo = ref<any>({})

function formatStatus(status:string|null){
    const labels:Record<string, string>={
        OPEN:"开放",
        CLOSED:"已关闭",
        SELECTED:"已选择",
        WAITING:"等待中",
        FINAL:"已录取",
        REJECTED:"未录取"
    }

    return status ? labels[status] || status : "未选择"
}





// 获取课程

async function loadCourses(){


    try{


        const res=await getCourses()


        courses.value=res.data



    }catch(error){


        ElMessage.error(
            "获取课程失败"
        )

    }


}


async function loadProfile(){

    try{

        const res=await getProfile()

        student.value=res.data

    }catch(error){

        ElMessage.error(
            "获取学生信息失败"
        )

    }
}





// 选课

async function handleSelect(
    id:number
){
    if(pendingCourse.value!==null) return
    pendingCourse.value=id

    try{


        await selectCourse(id)


        ElMessage.success(
            "选课成功"
        )


    }catch(error:any){


        ElMessage.error(

            error.response?.data?.detail
            ||
            (error.response ? "选课失败" : "未收到选课结果，正在刷新记录，请确认后再操作")

        )


    }finally{
        // Even a timed-out response may already have committed on the server.
        await Promise.all([loadCourses(), loadProfile()])
        pendingCourse.value=null
    }

}


// 查看排名

async function handleRank(
    id:number
){


    try{


        const res=await getRank(id)



        rankInfo.value=res.data



        rankVisible.value=true



    }catch(error:any){


        ElMessage.error(

            error.response?.data?.detail
            ||
            "查询失败"

        )


    }

}





// 退课

async function handleCancel(
    id:number
){
    if(pendingCourse.value!==null) return
    pendingCourse.value=id

    try{


        await cancelCourse(id)



        ElMessage.success(
            "退课成功"
        )


    }catch(error:any){


        ElMessage.error(

            error.response?.data?.detail
            ||
            (error.response ? "退课失败" : "未收到退课结果，正在刷新记录，请确认后再操作")

        )


    }finally{
        await Promise.all([loadCourses(), loadProfile()])
        pendingCourse.value=null
    }

}


function handlePasswordChanged(){

    passwordRequired.value=false
    loadCourses()
    loadProfile()

}

function formatProfileSelection(selection:StudentSelection){
    if(selection.status==="REJECTED") return "未录取（可参加后续选课）"
    if(selection.period_status==="CLOSED" && selection.status==="WAITING"){
        return "未录取"
    }
    return formatStatus(selection.status)
}


onMounted(()=>{

    if(!passwordRequired.value){
        loadCourses()
        loadProfile()
    }


})


</script>





<template>


<div class="student-page">


<header class="header">

<div class="header__title">
<span class="eyebrow">COURSE SELECTION</span>
<h2>学生选课中心</h2>
<p>选择适合你的课程，开启本学期的学习计划</p>
</div>

<div class="header__tools">
<div class="student-profile">
<div class="student-profile__avatar">{{student.name.slice(0, 1)}}</div>
<div>
<strong>学生：{{student.name}}</strong>
<span>学号：{{student.student_no || "加载中"}}</span>
</div>
</div>
<el-button class="logout-button" @click="passwordVisible=true">修改密码</el-button>
<el-button class="logout-button" @click="logout">退出登录</el-button>
</div>

</header>


<section class="welcome-panel">
<div>
<span class="welcome-panel__label">{{courses[0]?.period_name || "本学期选课"}}</span>
<h1>把感兴趣的课程，<em>加入你的计划。</em></h1>
<p v-if="courses.length">当前仅展示正在进行轮次的待选课程，每名学生最多选择两门兴趣课。</p>
<p v-else>当前没有正在进行的选课轮次，请留意后续通知。</p>
</div>
<div class="welcome-panel__shape">学</div>
</section>


<section class="overview-grid" aria-label="选课概览">
<div class="overview-item">
<span class="overview-item__label">全部课程</span>
<strong>{{courses.length}}</strong>
<span class="overview-item__hint">可浏览课程</span>
</div>
<div class="overview-item overview-item--teal">
<span class="overview-item__label">我的选择</span>
<strong>{{currentSelections.length}} / 2</strong>
<span class="overview-item__hint">已加入课程</span>
</div>
<div class="overview-item overview-item--gold">
<span class="overview-item__label">已录取</span>
<strong>{{finalSelectionCount}}</strong>
<span class="overview-item__hint">最终确认</span>
</div>
</section>


<div class="section-heading">
<div>
<span class="section-heading__eyebrow">COURSES</span>
<h2>课程列表</h2>
</div>
<span class="course-count">{{courses.length}} 门课程</span>
</div>


<el-alert
v-for="selection in student.selections"
:key="`${selection.period_id}-${selection.course_id}`"
:title="`选课记录：${selection.course_name}（${formatProfileSelection(selection)}）`"
:type="selection.status==='FINAL' ? 'success' : selection.status==='REJECTED' ? 'info' : 'warning'"
show-icon
:closable="false"
style="margin-bottom:12px"
/>

<div v-if="courses.length === 0" class="empty-state">
<div class="empty-state__icon">课</div>
<h3>当前没有进行中的选课轮次</h3>
<p>轮次开始后，本轮可选课程会显示在这里。</p>
</div>


<div class="course-cards">

<article
v-for="course in courses"
:key="course.id"
class="course-card"
>

<div class="course-card__top">
<div>
<h3>{{course.name}}</h3>
<p>{{course.description}}</p>
</div>


<el-tag
:type="course.selection_status==='FINAL' ? 'success' : course.is_selected ? 'warning' : 'info'"
>
{{course.selection_status==='FINAL' ? '已录取' : course.is_selected ? formatStatus(course.selection_status) : formatStatus(course.status)}}
</el-tag>
</div>

<div class="course-card__meta">
<span>容量 {{course.capacity}}</span>
<span>容量内 {{course.selected_count}}</span>
<span v-if="course.instructor">教师 {{course.instructor}}</span>
<span v-if="course.schedule">时间 {{course.schedule}}</span>
<span v-if="course.location">地点 {{course.location}}</span>
</div>

<div class="course-card__actions">
<el-button
v-if="!course.is_selected"
type="primary"
class="touch-button"
@click="handleSelect(course.id)"
:disabled="!course.can_select || pendingCourse!==null"
:loading="pendingCourse===course.id"
>
选课
</el-button>

<el-button
v-if="course.is_selected && course.period_active && course.selection_status!=='FINAL'"
class="touch-button"
@click="handleRank(course.id)"
>
查看排名
</el-button>

<el-button
v-if="course.is_selected && course.period_active && course.selection_status!=='FINAL'"
type="danger"
class="touch-button"
@click="handleCancel(course.id)"
:disabled="pendingCourse!==null"
:loading="pendingCourse===course.id"
>
退课
</el-button>
</div>

</article>
</div>


<el-table

class="desktop-table"

:data="courses"

border

>



<el-table-column

prop="name"

label="课程名称"

/>



<el-table-column

prop="description"

label="课程介绍"

/>

<el-table-column prop="instructor" label="教师" />

<el-table-column prop="schedule" label="上课时间" />

<el-table-column prop="location" label="地点" />



<el-table-column

prop="capacity"

label="容量"

/>



<el-table-column

prop="selected_count"

label="容量内人数"

/>



<el-table-column

prop="status"

label="状态"

>
<template #default="scope">
{{formatStatus(scope.row.status)}}
</template>
</el-table-column>





<el-table-column

label="操作"

width="260"

>


<template #default="scope">



<!-- 未选课程 -->

<el-button

v-if="!scope.row.is_selected"

type="primary"

@click="handleSelect(scope.row.id)"

:disabled="!scope.row.can_select || pendingCourse!==null"
:loading="pendingCourse===scope.row.id"

>

选课

</el-button>





<!-- 已选课程 -->

<el-button

v-if="
scope.row.is_selected
&&
scope.row.period_active
&&
scope.row.selection_status!=='FINAL'
"

type="success"

@click="handleRank(scope.row.id)"

>

排名

</el-button>





<el-button

v-if="scope.row.is_selected
&&
scope.row.period_active
&&
scope.row.selection_status!=='FINAL'
"

type="danger"

@click="handleCancel(scope.row.id)"
:disabled="pendingCourse!==null"
:loading="pendingCourse===scope.row.id"

>

退课

</el-button>





<!-- FINAL状态 -->

<el-tag

v-if="
scope.row.selection_status==='FINAL'
"

type="warning"

>

已录取

</el-tag>



</template>


</el-table-column>




</el-table>





<el-dialog

v-model="rankVisible"

title="我的排名"

width="400px"

>


<p>
学生ID：
{{rankInfo.student_id}}
</p>


<p>
当前排名：
第 {{rankInfo.rank}} 名
</p>


<p>
课程容量：
{{rankInfo.capacity}}
</p>


<p>
状态：
{{formatStatus(rankInfo.status)}}
</p>



</el-dialog>

<ChangePasswordDialog
v-model="passwordVisible"
:required="passwordRequired"
@password-changed="handlePasswordChanged"
/>



</div>


</template>


<style scoped>
.student-page{
    min-height:100vh;
    box-sizing:border-box;
    padding:42px clamp(18px, 5vw, 76px) 64px;
    color:#18323a;
    background:#f5f7f4;
    background-image:linear-gradient(135deg, rgba(212, 229, 218, .34), transparent 42%);
}

.header{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:28px;
    margin-bottom:30px;
}

.header h2{
    margin:4px 0 6px;
    color:#173b3d;
    font-size:30px;
    letter-spacing:0;
}

.header p{color:#718187;font-size:14px}
.eyebrow,.section-heading__eyebrow{color:#bf6b3b;font-size:11px;font-weight:800;letter-spacing:1.8px}
.header__tools{display:flex;align-items:center;gap:20px}
.student-profile{display:flex;align-items:center;gap:11px;padding-right:20px;border-right:1px solid #d8e0da}
.student-profile__avatar{display:grid;place-items:center;width:40px;height:40px;border-radius:50%;color:#fff;background:#1d6460;font-size:17px;font-weight:700}
.student-profile strong,.student-profile span{display:block;white-space:nowrap}
.student-profile strong{color:#24434a;font-size:14px}
.student-profile span{margin-top:3px;color:#7d8c90;font-size:12px}
.logout-button{border:1px solid #d5dfdb;color:#4f686d;background:#fff}
.logout-button:hover{color:#b45535;border-color:#e1b9a9;background:#fff8f5}

.welcome-panel{position:relative;display:flex;justify-content:space-between;overflow:hidden;min-height:170px;padding:32px 38px;box-sizing:border-box;border-radius:18px;color:#fff;background:#1c5553;box-shadow:0 16px 32px rgba(28,85,83,.16)}
.welcome-panel:after{content:"";position:absolute;width:310px;height:310px;right:-100px;top:-170px;border:1px solid rgba(255,255,255,.18);border-radius:50%;box-shadow:0 0 0 28px rgba(255,255,255,.04),0 0 0 56px rgba(255,255,255,.04)}
.welcome-panel__label{color:#b9ded1;font-size:12px;letter-spacing:1.4px;text-transform:uppercase}
.welcome-panel h1{margin:13px 0 8px;color:#fff;font-size:28px;line-height:1.3;letter-spacing:0}
.welcome-panel h1 em{color:#f5c895;font-style:normal}
.welcome-panel p{color:#c9dfd8;font-size:14px}
.welcome-panel__shape{align-self:center;z-index:1;margin-right:8%;color:#d9eee6;font-family:serif;font-size:96px;line-height:1;opacity:.25;transform:rotate(-10deg)}
.overview-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:22px 0 38px}
.overview-item{padding:20px 22px;border:1px solid #e4ddd5;border-radius:12px;background:#fffdf9}
.overview-item--teal{border-color:#c9dfda;background:#f6fbf9}
.overview-item--gold{border-color:#ecddc5;background:#fffaf1}
.overview-item__label,.overview-item__hint{display:block;color:#718187;font-size:13px}
.overview-item strong{display:block;margin:6px 0 1px;color:#173b3d;font-size:28px;line-height:1.2}
.overview-item__hint{color:#9aa4a1;font-size:12px}
.section-heading{display:flex;align-items:end;justify-content:space-between;margin-bottom:14px}
.section-heading h2{margin:4px 0 0;color:#173b3d;font-size:23px;letter-spacing:0}
.course-count{color:#82908f;font-size:13px}
.course-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:16px}
.course-card{display:flex;min-height:220px;flex-direction:column;padding:22px;border:1px solid #e3e8e3;border-radius:12px;background:#fff;box-shadow:0 8px 20px rgba(33,60,53,.05);transition:transform .2s ease,box-shadow .2s ease}
.course-card:hover{transform:translateY(-3px);box-shadow:0 14px 26px rgba(33,60,53,.1)}
.course-card__top,.course-card__meta,.course-card__actions{display:flex;align-items:center;justify-content:space-between;gap:12px}
.course-card__top{align-items:flex-start}
.course-card h3{margin:0 0 7px;color:#1c4145;font-size:18px}
.course-card p{color:#76868a;font-size:13px;line-height:1.6}
.course-card__meta{justify-content:flex-start;margin:20px 0;color:#899693;font-size:12px}
.course-card__actions{justify-content:flex-start;margin-top:auto}
.course-card__actions .el-button{margin:0}
.empty-state{padding:56px 20px;text-align:center;border:1px dashed #cddbd3;border-radius:12px;background:rgba(255,255,255,.65)}
.empty-state__icon{display:grid;place-items:center;width:42px;height:42px;margin:0 auto 12px;border-radius:50%;color:#1d6460;background:#e2f0e9;font-size:25px}
.empty-state h3{margin:0 0 5px;color:#29484b;font-size:17px}
.empty-state p{color:#8a9896;font-size:13px}
.desktop-table{display:none}

@media (max-width: 760px){
    .student-page{padding:24px 14px 40px}
    .header{align-items:flex-start;flex-direction:column;margin-bottom:20px}
    .header h2{font-size:25px}
    .header__tools{width:100%;justify-content:space-between;gap:10px}
    .student-profile{padding-right:10px}
    .logout-button{padding:0 12px}
    .welcome-panel{min-height:190px;padding:24px;}
    .welcome-panel h1{font-size:23px}
    .welcome-panel p{max-width:80%;line-height:1.6}
    .welcome-panel__shape{position:absolute;right:10px;bottom:12px;margin:0;font-size:74px}
    .overview-grid{gap:8px;margin:16px 0 28px}
    .overview-item{padding:14px 12px}
    .overview-item strong{font-size:23px}
    .overview-item__label,.overview-item__hint{font-size:11px}
}

@media (min-width: 761px){
    .course-cards{display:none}
    .desktop-table{display:table;margin-top:0}
}

</style>
