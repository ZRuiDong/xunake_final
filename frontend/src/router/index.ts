import {
    createRouter,
    createWebHistory
} from "vue-router"



const router=createRouter({

    history:createWebHistory(),


    routes:[


        {
            path:"/",

            redirect:"/login"

        },


        {
            path:"/login",

            component:
            ()=>import(
                "../views/Login.vue"
            )

        },


        {
            path:"/student",

            component:
            ()=>import(
                "../views/student/Home.vue"
            ),

            meta:{

                role:"STUDENT"

            }

        },


        {
            path:"/admin",

            component:
            ()=>import(
                "../layout/AdminLayout.vue"
            ),

            meta:{

                role:"ADMIN"

            },

            children:[

                {
                    path:"",

                    component:
                    ()=>import(
                        "../views/admin/Home.vue"
                    )

                },

                {
                    path:"student",

                    component:
                    ()=>import(
                        "../views/admin/Student.vue"
                    )

                },

                {
                    path:"period",

                    component:
                    ()=>import(
                        "../views/admin/Period.vue"
                    )

                },

                {
                    path:"period/:id",

                    component:
                    ()=>import(
                        "../views/admin/PeriodDetail.vue"
                    )

                }

            ]

        }


    ]

})



router.beforeEach(
    (to)=>{


        const token=
            localStorage.getItem(
                "token"
            )


        const role=
            localStorage.getItem(
                "role"
            )



        // 未登录

        if(
            to.path!=="/login"
            &&
            !token
        ){

            return "/login"

        }



        // 需要角色权限


        if(
            to.meta.role
            &&
            to.meta.role!==role
        ){

            if(role==="ADMIN"){

                return "/admin"

            }


            if(role==="STUDENT"){

                return "/student"

            }


            return "/login"

        }



        return true


    }
)



export default router
