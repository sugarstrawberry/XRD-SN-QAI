import numpy as np
import torch
from utils.HybridFeatureDataset import extract_physical_features
from utils.dataload import get_simxrd_d_grid
from models.PhyNetCNN import Model
from models.test import predict_xrd_api
import json

def process_single_npy_data(npy_file_path):
    """
    处理单条npy数据，提取物理特征
    
    Args:
        npy_file_path: npy文件路径
        
    Returns:
        tuple: (raw_xrd_data, physical_features)
    """
    print(f"处理单条XRD数据: {npy_file_path}")
    
    # 加载npy数据
    try:
        intensity_data = np.load(npy_file_path)
        print(f"✓ 成功加载数据，形状: {intensity_data.shape}")
    except Exception as e:
        print(f"❌ 加载npy文件失败: {e}")
        return None, None
    
    # 获取对应的d-spacing网格
    # 根据generate_npy_data.py，我们使用dataload.py的网格
    d_grid = get_simxrd_d_grid()
    print(f"✓ d-spacing网格: {len(d_grid)}个点，范围 {d_grid.min():.3f}-{d_grid.max():.3f} Å")
    
    # 检查数据长度是否匹配
    if len(intensity_data) != len(d_grid):
        print(f"⚠️  数据长度不匹配: 强度数据{len(intensity_data)}，网格{len(d_grid)}")
        # 如果长度不匹配，进行插值调整
        if len(intensity_data) == 5000:  # 如果是5000点的数据
            print("检测到5000点数据，使用对应的d-spacing网格")
            d_grid = np.linspace(0.889, 17.659, 5000)
        else:
            print("❌ 无法处理的数据长度")
            return None, None
    
    # 提取物理特征
    try:
        physical_features = extract_physical_features(d_grid, intensity_data, num_peaks=10)
        print(f"✓ 物理特征提取完成，特征维度: {len(physical_features)}")
        
        # 显示特征统计
        print(f"  - 特征范围: {physical_features.min():.3f} - {physical_features.max():.3f}")
        print(f"  - 非零特征数: {np.count_nonzero(physical_features)}")
        
    except Exception as e:
        print(f"❌ 物理特征提取失败: {e}")
        return None, None
    
    return intensity_data, physical_features

def load_model(model_path, device='cuda'):
    """
    加载预训练模型
    
    Args:
        model_path: 模型文件路径
        device: 计算设备
        
    Returns:
        model: 加载的模型
    """
    print(f"加载模型: {model_path}")
    
    try:
        # 设置设备
        device = torch.device(device if torch.cuda.is_available() else 'cpu')
        print(f"使用设备: {device}")
        
        # 创建模型
        model = Model()
        
        # 加载权重
        model.load_state_dict(torch.load(model_path, map_location=device))
        model = model.to(device)
        model.eval()
        
        print("✓ 模型加载成功")
        return model, device
        
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        return None, None

def predict_single_xrd(npy_file_path, model_path=None, T=50):
    """
    对单条XRD数据进行预测
    
    Args:
        npy_file_path: npy数据文件路径
        model_path: 模型文件路径
        T: MC Dropout采样次数
        
    Returns:
        dict: 预测结果
    """
    print("=" * 60)
    print("XRD单条数据预测")
    print("=" * 60)
    
    # 1. 处理数据
    raw_xrd, physical_features = process_single_npy_data(npy_file_path)
    if raw_xrd is None or physical_features is None:
        return None
    
    # 2. 加载模型
    if model_path:
        model, device = load_model(model_path)
        if model is None:
            return None
    else:
        print("⚠️  未提供模型路径，使用随机初始化的模型进行演示")
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = Model().to(device)
        model.eval()
    
    # 3. 进行预测
    print(f"\n开始预测 (MC Dropout采样次数: {T})")
    try:
        results = predict_xrd_api(model, raw_xrd, physical_features, device, T=T)
        print("✓ 预测完成")
        return results
        
    except Exception as e:
        print(f"❌ 预测失败: {e}")
        return None

def display_results(results):
    """
    显示预测结果
    
    Args:
        results: predict_xrd_api返回的结果
    """
    if results is None:
        print("无预测结果可显示")
        return
    
    print("\n" + "=" * 60)
    print("预测结果")
    print("=" * 60)
    
    # 显示全局不确定性
    print(f"全局不确定性 (熵): {results['global_uncertainty']:.4f}")
    
    # 显示Top-5预测
    print(f"\nTop-5 空间群预测:")
    print("-" * 50)
    print(f"{'排名':<4} {'空间群':<8} {'概率':<12} {'标准差':<12} {'置信度'}")
    print("-" * 50)
    
    for pred in results['top_5_predictions']:
        rank = pred['rank']
        space_group = pred['label'] + 1  # 空间群从1开始编号
        prob = pred['probability']
        std = pred['std_dev']
        confidence = "高" if std < 0.01 else "中" if std < 0.05 else "低"
        
        print(f"{rank:<4} {space_group:<8} {prob:<12.4f} {std:<12.4f} {confidence}")
    
    # 预测解读
    print(f"\n预测解读:")
    print("-" * 30)
    top_pred = results['top_5_predictions'][0]
    top_space_group = top_pred['label'] + 1
    top_prob = top_pred['probability']
    top_std = top_pred['std_dev']
    
    print(f"最可能的空间群: {top_space_group}")
    print(f"预测概率: {top_prob:.2%}")
    print(f"模型置信度: {'高' if top_std < 0.01 else '中' if top_std < 0.05 else '低'}")
    
    if results['global_uncertainty'] < 2.0:
        print("整体预测: 模型对此样品较为确定")
    elif results['global_uncertainty'] < 4.0:
        print("整体预测: 模型对此样品有一定不确定性")
    else:
        print("整体预测: 模型对此样品不确定性较高")

def save_results(results, output_file='prediction_results.json'):
    """
    保存预测结果到JSON文件
    
    Args:
        results: 预测结果
        output_file: 输出文件路径
    """
    if results is None:
        return
    
    try:
        # 添加额外信息
        output_data = {
            'prediction_info': {
                'model_type': 'PhyNetCNN with MC Dropout',
                'input_data': 'Single XRD pattern',
                'timestamp': str(np.datetime64('now'))
            },
            'results': results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 预测结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"❌ 保存结果失败: {e}")

if __name__ == '__main__':
    # 配置参数
    npy_file = 'test_xrd_data.npy'  # 输入的npy文件
    model_path = None  # 模型文件路径，如果没有则使用None
    # model_path = 'path/to/your/model.pth'  # 如果有训练好的模型，取消注释并修改路径
    
    sampling_times = 50  # MC Dropout采样次数
    
    print("XRD晶体结构预测系统")
    print("基于PhyNetCNN模型和Monte Carlo Dropout不确定性估计")
    
    # 执行预测
    results = predict_single_xrd(npy_file, model_path, T=sampling_times)
    
    # 显示结果
    display_results(results)
    
    # 保存结果
    if results:
        save_results(results, 'xrd_prediction_results.json')
        
        print(f"\n" + "=" * 60)
        print("预测完成!")
        print("=" * 60)
        print("生成的文件:")
        print("  - xrd_prediction_results.json (详细预测结果)")
        print("\n使用说明:")
        print("  1. 确保有训练好的模型文件")
        print("  2. 修改model_path变量指向你的模型文件")
        print("  3. 重新运行获得准确的预测结果")
    else:
        print("\n❌ 预测失败，请检查输入数据和模型文件")