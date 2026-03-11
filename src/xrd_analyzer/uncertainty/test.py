import torch
import torch.nn.functional as F
import numpy as np


def enable_dropout(model):
    """
    在推理时强制开启 Dropout 层，这是 MC Dropout 的核心。
    """
    for m in model.modules():
        if m.__class__.__name__.startswith('Dropout'):
            m.train()


def predict_xrd_api(model, xrd_input, phys_input, device, T=50):
    """
    接收单条数据，执行 MC Dropout 推理，返回 Top-5 结果及不确定性。
    
    Args:
        model: 已加载的 PyTorch 模型
        xrd_input: 原始 XRD 数据 (list or numpy array)
        phys_input: 物理特征数据 (list or numpy array)
        device: 'cuda' 或 'cpu'
        T: MC Dropout 采样次数
        
    Returns:
        dict: 包含 Top-5 预测结果列表和全局不确定性指标的字典
    """

    xrd_tensor = torch.tensor(xrd_input, dtype=torch.float32).unsqueeze(0).to(device)
    phys_tensor = torch.tensor(phys_input, dtype=torch.float32).unsqueeze(0).to(device)
    
    model.eval()
    enable_dropout(model)
    
    batch_probs = []
    
    with torch.no_grad():
        for _ in range(T):
            # 前向传播
            outputs = model(xrd_tensor, phys_tensor)
            # 计算 Softmax 概率
            probs = F.softmax(outputs, dim=1)
            batch_probs.append(probs.unsqueeze(0)) # 形状: [1, 1, Num_Classes]
            
    all_probs_tensor = torch.cat(batch_probs, dim=0)
    
    mean_probs = all_probs_tensor.mean(dim=0)
    
    std_probs = all_probs_tensor.std(dim=0)
    
    entropy = -torch.sum(mean_probs * torch.log(mean_probs + 1e-9), dim=1).item()
    
    top5_probs, top5_indices = torch.topk(mean_probs, k=5, dim=1)
    
    top5_indices = top5_indices.cpu().numpy()[0]
    top5_probs = top5_probs.cpu().numpy()[0]
    
    top5_std = std_probs[0, top5_indices].cpu().numpy()
    

    results = []
    for rank in range(5):
        idx = int(top5_indices[rank])
        results.append({
            "rank": rank + 1,
            "label": idx,                   # 类别索引 (如果标签从1开始，请改为 idx + 1)
            "probability": float(top5_probs[rank]),  # 平均概率
            "std_dev": float(top5_std[rank])         # 该概率的标准差 (模型对该类别的“犹豫”程度)
        })
        
    response_data = {
        "global_uncertainty": float(entropy), # 整体样本的不确定性 (熵)
        "top_5_predictions": results
    }
    
    return response_data

if __name__ == "__main__":
    model = PhyNetCNN.Model().to(device)
    model.load_state_dict(torch.load('training_results/exp_results/exp_test4_model.pth'))