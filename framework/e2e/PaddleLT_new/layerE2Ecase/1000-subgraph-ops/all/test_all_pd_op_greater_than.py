import os
os.environ['FLAGS_cinn_new_group_scheduler'] = '1'
os.environ['FLAGS_group_schedule_tiling_first'] = '1'
os.environ['FLAGS_enable_pir_api'] = '1'
os.environ['FLAGS_cinn_bucket_compile'] = '1'
import sys
import unittest
import numpy as np
from dataclasses import dataclass
import typing as t

@dataclass
class Stage:
    name: str
    env_vars: t.Dict[str, str]

cinn_stages = [
    Stage(
        name="dynamic_to_static",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=False,
            FLAGS_prim_enable_dynamic=False,
        ),
    ),
    Stage(
        name="prim",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
        ),
    ),
    Stage(
        name="infer_symbolic",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=False,
            FLAGS_check_infer_symbolic=True,
        ),
    ),
	Stage(
        name="frontend",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=True,
            FLAGS_check_infer_symbolic=False,
            FLAGS_enable_fusion_fallback=True,
        ), 
    ),
    Stage(
        name="backend",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=True,
            FLAGS_check_infer_symbolic=False,
            FLAGS_enable_fusion_fallback=False,
        ), 
    ),
]

def GetCinnStageByName(name):
    for stage in cinn_stages:
        if stage.name == name:
            return stage
    return None

def GetCurrentCinnStage():
    name = os.getenv('PADDLE_DEBUG_CINN_STAGE_NAME')
    if name is None:
        return None
    stage_names = [stage.name for stage in cinn_stages]
    assert name in stage_names, (
        f"PADDLE_DEBUG_CINN_STAGE_NAME should be in {stage_names}"
    )
    return GetCinnStageByName(name)

def GetPrevCinnStage(stage):
    for i in range(1, len(cinn_stages)):
        if stage is cinn_stages[i]:
            return cinn_stages[i - 1]
    return None

def IsCinnStageEnableDiff():
    value = os.getenv('PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF')
    enabled = value in {
        '1',
        'true',
        'True',
    }
    if enabled:
        assert GetCurrentCinnStage() is not None
    return enabled

last_cinn_stage_exit_code = None
def LastCINNStageFailed():
    global last_cinn_stage_exit_code
    if last_cinn_stage_exit_code is not None:
        return last_cinn_stage_exit_code != 0
    last_stage = GetPrevCinnStage(GetCurrentCinnStage())
    if last_stage is None:
        return False
    env_vars = dict(
        PADDLE_DEBUG_CINN_STAGE_NAME=last_stage.name,
        PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF='0',
    )
    env_vars_str = " ".join(
        f"{env_var}={value}"
        for env_var, value in env_vars.items()
    )
    last_cinn_stage_exit_code = os.system(
        f"{env_vars_str} {sys.executable} {__file__} > /dev/null 2>&1"
    )
    return last_cinn_stage_exit_code != 0

def SetDefaultEnv(**env_var2value):
    for env_var, value in env_var2value.items():
        if os.getenv(env_var) is None:
            os.environ[env_var] = str(value)

SetDefaultEnv(
    PADDLE_DEBUG_ENABLE_CINN=True,
    FLAGS_enable_pir_api=True,
    FLAGS_prim_all=True,
    FLAGS_prim_enable_dynamic=True,
    FLAGS_use_cinn=False,
    FLAGS_check_infer_symbolic=False,
    FLAGS_enable_fusion_fallback=False,
)

import paddle

def SetEnvVar(env_var2value):
    for env_var, value in env_var2value.items():
        os.environ[env_var] = str(value)
    paddle.set_flags({
        env_var:value
        for env_var, value in env_var2value.items()
        if env_var.startswith('FLAGS_')
    })

if GetCurrentCinnStage() is not None:
    SetEnvVar(GetCurrentCinnStage().env_vars)

def GetEnvVarEnableJit():
    enable_jit = os.getenv('PADDLE_DEBUG_ENABLE_JIT')
    return enable_jit not in {
        "0",
        "False",
        "false",
        "OFF",
    }

def GetEnvVarEnableCinn():
    enable_cinn = os.getenv('PADDLE_DEBUG_ENABLE_CINN')
    if enable_cinn is None:
        return True
    return enable_cinn not in {
        "0",
        "False",
        "false",
        "OFF",
    }


def GetTolerance(dtype):
    if dtype == np.float16:
        return GetFloat16Tolerance()
    if dtype == np.float32:
        return GetFloat32Tolerance()
    return 1e-6

def GetFloat16Tolerance():
    try:
        return float(os.getenv('PADDLE_DEBUG_FLOAT16_TOL'))
    except:
        return 1e-3

def GetFloat32Tolerance():
    try:
        return float(os.getenv('PADDLE_DEBUG_FLOAT32_TOL'))
    except:
        return 1e-6

def IsInteger(dtype):
    return np.dtype(dtype).char in np.typecodes['AllInteger']

def ApplyToStatic(net, use_cinn):
    build_strategy = paddle.static.BuildStrategy()
    build_strategy.build_cinn_pass = use_cinn
    return paddle.jit.to_static(
        net,
        input_spec=net.get_input_spec(),
        build_strategy=build_strategy,
        full_graph=True,
    )

class InstanceTrait:

    @classmethod
    def instance(cls):
        if cls.instance_ is None:
            cls.instance_ = cls()
        return cls.instance_

    @classmethod
    def static_instance_with_cinn(cls):
        if cls.static_instance_with_cinn_ is None:
            cls.static_instance_with_cinn_ = ApplyToStatic(
                cls.instance(),
                use_cinn=True
            )
        return cls.static_instance_with_cinn_

    @classmethod
    def static_instance_without_cinn(cls):
        if cls.static_instance_without_cinn_ is None:
            cls.static_instance_without_cinn_ = ApplyToStatic(
                cls.instance(),
                use_cinn=False
            )
        return cls.static_instance_without_cinn_


class CinnTestBase:

    def setUp(self):
        paddle.seed(2024)
        self.prepare_data()

    def test_train(self):
        dy_outs = self.train(use_cinn=False)
        cinn_outs = self.train(use_cinn=GetEnvVarEnableCinn())

        for cinn_out, dy_out in zip(cinn_outs, dy_outs):
          if type(cinn_out) is list and type(dy_out) is list:
            for x, y in zip(cinn_out, dy_out):
              self.assert_all_close(x, y)
          else:
            self.assert_all_close(cinn_out, dy_out)

    def train(self, use_cinn):
        if GetEnvVarEnableJit():
            net = self.prepare_static_net(use_cinn)
        else:
            net = self.prepare_net()
        paddle.seed(2024)
        out = net(*self.inputs)
        return out
    
    def prepare_data(self):
        self.inputs = self.get_inputs()
        for input in self.inputs:
            input.stop_gradient = True

    def prepare_net(self):
        return self.get_test_class().instance()

    def prepare_static_net(self, use_cinn):
        if use_cinn:
            return self.get_test_class().static_instance_with_cinn()
        else:
            return self.get_test_class().static_instance_without_cinn()

    def assert_all_close(self, x, y):
        if (hasattr(x, "numpy") and hasattr(y, "numpy")):
            x_numpy = x.numpy()
            y_numpy = y.numpy()
            assert x_numpy.dtype == y_numpy.dtype
            if IsInteger(x_numpy.dtype):
                np.testing.assert_equal(x_numpy, y_numpy)
            else:
                tol = GetTolerance(x_numpy.dtype)
                np.testing.assert_allclose(x_numpy, y_numpy, atol=tol, rtol=tol)
        else:
            assert x == y





if not (IsCinnStageEnableDiff() and LastCINNStageFailed()):
    class PrimitiveOp_9f67948c90a27dedc69dc9c29abce9a4(InstanceTrait, paddle.nn.Layer):
        
        def __init__(self):
            super().__init__()

        def forward(self, arg_0, arg_1):
            input_0 = arg_0
            input_1 = arg_1
            return input_0 > input_1

        def get_input_spec(self):
            return [
                paddle.static.InputSpec(shape=[None, None], dtype='float32'),
                paddle.static.InputSpec(shape=[], dtype='float32'),
            ]
            
        instance_ = None
        static_instance_with_cinn_ = None
        static_instance_without_cinn_ = None


    class TestPrimitiveOp_4e1e578f62b8d00eb9809b90efc66962(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_9f67948c90a27dedc69dc9c29abce9a4
        def get_inputs(self):
            return [
                paddle.uniform([1, 2100], dtype='float32', min=0, max=0.5),
                paddle.to_tensor(0.0, dtype='float32').reshape([]),
            ]


    
    class PrimitiveOp_8bbe8eddb0a46c81fbb21a582ddcd959(InstanceTrait, paddle.nn.Layer):
        
        def __init__(self):
            super().__init__()

        def forward(self, arg_0, arg_1):
            input_0 = arg_0
            input_1 = arg_1
            return input_0 > input_1

        def get_input_spec(self):
            return [
                paddle.static.InputSpec(shape=[1, 500, 128], dtype='int32'),
                paddle.static.InputSpec(shape=[], dtype='int32'),
            ]
            
        instance_ = None
        static_instance_with_cinn_ = None
        static_instance_without_cinn_ = None


    class TestPrimitiveOp_7b29b2942ddd8a97bd024a462e607e6f(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_8bbe8eddb0a46c81fbb21a582ddcd959
        def get_inputs(self):
            return [
                paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_7b29b2942ddd8a97bd024a462e607e6f(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_8bbe8eddb0a46c81fbb21a582ddcd959
        def get_inputs(self):
            return [
                paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    
    class PrimitiveOp_11763d9bc05dc6e29371a4dc7597d907(InstanceTrait, paddle.nn.Layer):
        
        def __init__(self):
            super().__init__()

        def forward(self, arg_0, arg_1):
            input_0 = arg_0
            input_1 = arg_1
            return input_0 > input_1

        def get_input_spec(self):
            return [
                paddle.static.InputSpec(shape=[None], dtype='int32'),
                paddle.static.InputSpec(shape=[], dtype='int32'),
            ]
            
        instance_ = None
        static_instance_with_cinn_ = None
        static_instance_without_cinn_ = None


    class TestPrimitiveOp_d1dbda727913bbd330f6f1b84dd426a8(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_11763d9bc05dc6e29371a4dc7597d907
        def get_inputs(self):
            return [
                paddle.to_tensor([2, 6], dtype='int32').reshape([2]),
                paddle.to_tensor(-1, dtype='int32').reshape([]),
            ]


    
    class PrimitiveOp_8f0f08663d7651adbc9f117a3cdd685d(InstanceTrait, paddle.nn.Layer):
        
        def __init__(self):
            super().__init__()

        def forward(self, arg_0, arg_1):
            input_0 = arg_0
            input_1 = arg_1
            return input_0 > input_1

        def get_input_spec(self):
            return [
                paddle.static.InputSpec(shape=[None], dtype='float32'),
                paddle.static.InputSpec(shape=[None], dtype='float32'),
            ]
            
        instance_ = None
        static_instance_with_cinn_ = None
        static_instance_without_cinn_ = None


    class TestPrimitiveOp_5b1f055da079c02f0200372fd6d73c9a(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_8f0f08663d7651adbc9f117a3cdd685d
        def get_inputs(self):
            return [
                paddle.to_tensor([0.22168461978435516, 0.3048173189163208, 0.36503466963768005, 0.15319602191448212, 0.32081952691078186, 0.1342129111289978], dtype='float32').reshape([6]),
                paddle.to_tensor([0.49831607937812805, 0.37963253259658813, 0.39980247616767883, 0.4289640784263611, 0.32081952691078186, 0.11360201984643936], dtype='float32').reshape([6]),
            ]


    class TestPrimitiveOp_b0c398d6f94241121969d24b7abcbd41(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_8f0f08663d7651adbc9f117a3cdd685d
        def get_inputs(self):
            return [
                paddle.to_tensor([0.3236333429813385, 0.30897533893585205, 0.17026685178279877, 0.10646888613700867, 0.4039801359176636, 0.05345135182142258], dtype='float32').reshape([6]),
                paddle.to_tensor([0.3236333429813385, 0.14679817855358124, 0.3744381070137024, 0.4712778925895691, 0.4077642858028412, 0.37590494751930237], dtype='float32').reshape([6]),
            ]


    class TestPrimitiveOp_5ae79dff2e497d4804720245968ed289(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_11763d9bc05dc6e29371a4dc7597d907
        def get_inputs(self):
            return [
                paddle.to_tensor([6, 9], dtype='int32').reshape([2]),
                paddle.to_tensor(-1, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_05ab847a5cb8f7b976fdaa0c9e092cb5(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_9f67948c90a27dedc69dc9c29abce9a4
        def get_inputs(self):
            return [
                paddle.uniform([1, 3549], dtype='float32', min=0, max=0.5),
                paddle.to_tensor(0.0, dtype='float32').reshape([]),
            ]


    
    class PrimitiveOp_7f7cfc7a83934b722e430d25462aeb45(InstanceTrait, paddle.nn.Layer):
        
        def __init__(self):
            super().__init__()

        def forward(self, arg_0, arg_1):
            input_0 = arg_0
            input_1 = arg_1
            return input_0 > input_1

        def get_input_spec(self):
            return [
                paddle.static.InputSpec(shape=[1], dtype='int32'),
                paddle.static.InputSpec(shape=[], dtype='int32'),
            ]
            
        instance_ = None
        static_instance_with_cinn_ = None
        static_instance_without_cinn_ = None


    class TestPrimitiveOp_fcee0f833f7843e6d71833eebcd4b15e(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_7f7cfc7a83934b722e430d25462aeb45
        def get_inputs(self):
            return [
                paddle.to_tensor([7], dtype='int32').reshape([1]),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_33d3753cd44cf82a3ed381c11ce08a66(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_7f7cfc7a83934b722e430d25462aeb45
        def get_inputs(self):
            return [
                paddle.to_tensor([3], dtype='int32').reshape([1]),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_fac0abe6960f45b3684c4562e596fcf4(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_9f67948c90a27dedc69dc9c29abce9a4
        def get_inputs(self):
            return [
                paddle.uniform([1, 4116], dtype='float32', min=0, max=0.5),
                paddle.to_tensor(0.0, dtype='float32').reshape([]),
            ]


    class TestPrimitiveOp_7b29b2942ddd8a97bd024a462e607e6f(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_8bbe8eddb0a46c81fbb21a582ddcd959
        def get_inputs(self):
            return [
                paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_4e1e578f62b8d00eb9809b90efc66962(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_9f67948c90a27dedc69dc9c29abce9a4
        def get_inputs(self):
            return [
                paddle.uniform([1, 2100], dtype='float32', min=0, max=0.5),
                paddle.to_tensor(0.0, dtype='float32').reshape([]),
            ]


    
    class PrimitiveOp_075fa4c6beecac71b99634fa22625125(InstanceTrait, paddle.nn.Layer):
        
        def __init__(self):
            super().__init__()

        def forward(self, arg_0, arg_1):
            input_0 = arg_0
            input_1 = arg_1
            return input_0 > input_1

        def get_input_spec(self):
            return [
                paddle.static.InputSpec(shape=[None, None, None], dtype='int32'),
                paddle.static.InputSpec(shape=[], dtype='int32'),
            ]
            
        instance_ = None
        static_instance_with_cinn_ = None
        static_instance_without_cinn_ = None


    class TestPrimitiveOp_54e6fba96d48deb85bf6ff6ff6441e21(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_075fa4c6beecac71b99634fa22625125
        def get_inputs(self):
            return [
                paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_54e6fba96d48deb85bf6ff6ff6441e21(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_075fa4c6beecac71b99634fa22625125
        def get_inputs(self):
            return [
                paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_d1dbda727913bbd330f6f1b84dd426a8(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_11763d9bc05dc6e29371a4dc7597d907
        def get_inputs(self):
            return [
                paddle.to_tensor([2, 6], dtype='int32').reshape([2]),
                paddle.to_tensor(-1, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_5b1f055da079c02f0200372fd6d73c9a(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_8f0f08663d7651adbc9f117a3cdd685d
        def get_inputs(self):
            return [
                paddle.to_tensor([0.22168461978435516, 0.3048173189163208, 0.36503466963768005, 0.15319602191448212, 0.32081952691078186, 0.1342129111289978], dtype='float32').reshape([6]),
                paddle.to_tensor([0.49831607937812805, 0.37963253259658813, 0.39980247616767883, 0.4289640784263611, 0.32081952691078186, 0.11360201984643936], dtype='float32').reshape([6]),
            ]


    class TestPrimitiveOp_b0c398d6f94241121969d24b7abcbd41(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_8f0f08663d7651adbc9f117a3cdd685d
        def get_inputs(self):
            return [
                paddle.to_tensor([0.3236333429813385, 0.30897533893585205, 0.17026685178279877, 0.10646888613700867, 0.4039801359176636, 0.05345135182142258], dtype='float32').reshape([6]),
                paddle.to_tensor([0.3236333429813385, 0.14679817855358124, 0.3744381070137024, 0.4712778925895691, 0.4077642858028412, 0.37590494751930237], dtype='float32').reshape([6]),
            ]


    class TestPrimitiveOp_5ae79dff2e497d4804720245968ed289(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_11763d9bc05dc6e29371a4dc7597d907
        def get_inputs(self):
            return [
                paddle.to_tensor([6, 9], dtype='int32').reshape([2]),
                paddle.to_tensor(-1, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_05ab847a5cb8f7b976fdaa0c9e092cb5(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_9f67948c90a27dedc69dc9c29abce9a4
        def get_inputs(self):
            return [
                paddle.uniform([1, 3549], dtype='float32', min=0, max=0.5),
                paddle.to_tensor(0.0, dtype='float32').reshape([]),
            ]


    class TestPrimitiveOp_8e31059533eca126fd8f5ffc0bcf94e9(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_11763d9bc05dc6e29371a4dc7597d907
        def get_inputs(self):
            return [
                paddle.to_tensor([7], dtype='int32').reshape([1]),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_b0ab56e27cf4ac45d3168cc2ae3f6fda(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_11763d9bc05dc6e29371a4dc7597d907
        def get_inputs(self):
            return [
                paddle.to_tensor([3], dtype='int32').reshape([1]),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    class TestPrimitiveOp_fac0abe6960f45b3684c4562e596fcf4(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_9f67948c90a27dedc69dc9c29abce9a4
        def get_inputs(self):
            return [
                paddle.uniform([1, 4116], dtype='float32', min=0, max=0.5),
                paddle.to_tensor(0.0, dtype='float32').reshape([]),
            ]


    class TestPrimitiveOp_54e6fba96d48deb85bf6ff6ff6441e21(CinnTestBase, unittest.TestCase):
        
        def get_test_class(self):
            return PrimitiveOp_075fa4c6beecac71b99634fa22625125
        def get_inputs(self):
            return [
                paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
                paddle.to_tensor(0, dtype='int32').reshape([]),
            ]


    

if __name__ == '__main__':
    unittest.main()